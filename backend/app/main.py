from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from pathlib import Path
import uuid
import logging
import re
import os
import json
import traceback
from contextlib import contextmanager
from typing import Optional
from datetime import datetime

from .config import settings
from .database import Base, engine, SessionLocal
from . import models, schemas
from .auth import get_db, verify_google_id_token, get_current_user_google

app = FastAPI(title="Board Backend", version="1.1.1")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("board")

def _log_kv(prefix: str, **kv):
    try:
        msg = prefix + " | " + " ".join(f"{k}={v}" for k, v in kv.items())
        logger.info(msg)
    except Exception:
        logger.info(prefix)

def _get_allowed_origins() -> list[str]:
    raw = (os.getenv("APP_BACKEND_CORS_ORIGINS")
           or getattr(settings, "backend_cors_origins", "")
           or "").strip()
    if not raw:
        return ["http://localhost:3000"]
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return ["*"] if any(p == "*" for p in parts) else parts

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
    max_age=86400,
)

Base.metadata.create_all(bind=engine)

media_root = Path(settings.media_dir)
media_root.mkdir(parents=True, exist_ok=True)
for sub in ("videos", "ply", "traj", "points", "logs"):
    (media_root / sub).mkdir(parents=True, exist_ok=True)

app.mount("/media", StaticFiles(directory=str(media_root)), name="media")

_RAW_MARKETS = [
    "용두시장","B청량리농수산물시장","C경동시장","D동서시장","E전농로터리시장","F동부시장","G전곡시장","H이경시장","I이문제일시장",
    "K청량리청과물시장","L청량리종합시장","M서울약령시장","N경동광성상가","O청량리전통시장","P답십리현대시장","Q답십리시장",
    "R회기시장","S청량종합도매시장","T청량리수산시장","U답십리건축자재시장",
]
_ALPH_RE = re.compile(r"^[A-Z]\s*")
SANITIZED_MARKETS = []
for name in _RAW_MARKETS:
    clean = _ALPH_RE.sub("", name).strip()
    if clean and clean not in SANITIZED_MARKETS:
        SANITIZED_MARKETS.append(clean)

@app.get("/markets", response_model=list[str])
def list_markets():
    return SANITIZED_MARKETS

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.post("/auth/login", response_model=dict)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    info = verify_google_id_token(payload.id_token)
    sub = info.get("sub")
    exists = db.query(models.User).filter(models.User.google_sub == sub).first() is not None
    return {"signup_required": not exists}

@app.post("/auth/signup", response_model=schemas.SimpleOK)
def signup(payload: schemas.SignupRequest, db: Session = Depends(get_db)):
    info = verify_google_id_token(payload.id_token)
    sub = info.get("sub")
    email = info.get("email") or ""
    name = info.get("name")

    role = payload.role
    if role not in ("SELLER", "BUYER"):
        raise HTTPException(status_code=400, detail="invalid_role")

    store_name = payload.store_name
    market = payload.market
    stall_no = payload.stall_no
    if role == "SELLER":
        if not store_name:
            raise HTTPException(status_code=400, detail="store_name_required")
        if not market or market not in SANITIZED_MARKETS:
            raise HTTPException(status_code=400, detail="invalid_market")

    user = db.query(models.User).filter(models.User.google_sub == sub).first()
    if user:
        user.role = role
        if role == "SELLER":
            user.store_name = store_name
            user.market = market
            user.stall_no = stall_no or None
        else:
            user.store_name = None
            user.market = None
            user.stall_no = None
    else:
        user = models.User(
            google_sub=sub, email=email, name=name, role=role,
            store_name=store_name if role=="SELLER" else None,
            market=market if role=="SELLER" else None,
            stall_no=stall_no if role=="SELLER" else None,
        )
        db.add(user)
    db.commit()
    return {"ok": True}

@app.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(get_current_user_google)):
    return user

def _stats(db: Session, post_id: int) -> schemas.ReviewStats:
    qs = db.query(models.Review).filter(models.Review.post_id == post_id)
    total = qs.count()

    def c(field, val):
        return qs.filter(getattr(models.Review, field) == val).count()

    def pack(field, pos_alias=(), neu_alias=("mid",), neg_alias=()):
        pos = c(field, 1)
        neu = c(field, 0)
        neg = c(field, -1)
        d = {
            "1": pos, "0": neu, "-1": neg,
            "pos": pos, "neu": neu, "neg": neg,
        }
        for a in pos_alias: d[a] = pos
        for a in neu_alias: d[a] = neu
        for a in neg_alias: d[a] = neg
        return d

    return schemas.ReviewStats(
        total=total,
        kindness=pack("kindness", pos_alias=("positive",), neg_alias=("negative",)),
        price=pack("price",    pos_alias=("cheap",),       neg_alias=("exp",)),
        variety=pack("variety",pos_alias=("div",),         neg_alias=("low",)),
    )

@app.post("/posts/{post_id}/reviews", response_model=schemas.ReviewStats)
def upsert_review(
    post_id: int,
    payload: schemas.ReviewCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user_google),
):
    if not user:
        raise HTTPException(status_code=401, detail="unauthorized")
    if user.role != "BUYER":
        raise HTTPException(status_code=403, detail="forbidden")

    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="not_found")

    def norm(v: int) -> int:
        return 1 if v > 0 else (-1 if v < 0 else 0)

    k = norm(payload.kindness)
    p = norm(payload.price)
    v = norm(payload.variety)

    r = db.query(models.Review).filter_by(post_id=post_id, user_id=user.id).first()
    if r:
        r.kindness = k
        r.price = p
        r.variety = v
    else:
        r = models.Review(post_id=post_id, user_id=user.id, kindness=k, price=p, variety=v)
        db.add(r)

    db.commit()
    return _stats(db, post_id)

@app.get("/posts/{post_id}/reviews", response_model=schemas.ReviewStats)
def get_reviews_stats(post_id: int, db: Session = Depends(get_db)):
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="not_found")
    return _stats(db, post_id)

def _load_products_json_for_post(p: models.Post) -> Optional[list[dict]]:
    folder = None
    if p.video_path:
        folder = (media_root / p.video_path).parent
    elif p.ply_path:
        folder = (media_root / p.ply_path).parent
    if not folder:
        return None
    try:
        stem = folder.name
        candidates = [
            folder / f"{stem}.json",
            *sorted(folder.glob("*.json"))
        ]
        for cand in candidates:
            if cand.exists():
                with open(cand, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    out = []
                    for idx, it in enumerate(data):
                        if not isinstance(it, dict):
                            continue
                        item = {
                            "name": it.get("name"),
                            "price": it.get("price"),
                            "time_min": int(it.get("time_min", 0) or 0),
                            "time_sec": int(it.get("time_sec", 0) or 0),
                            "time_ms": int(it.get("time_ms", 0) or 0),
                        }
                        img_file = folder / "img" / f"{idx}.png"
                        if img_file.exists():
                            item["image_url"] = f"/media/{folder.name}/img/{idx}.png"
                        else:
                            item["image_url"] = None
                        out.append(item)
                    return out
        return None
    except Exception as e:
        logger.warning("products json load failed: %s", e)
        return None

def _post_out(p: models.Post, db: Session) -> schemas.PostOut:
    return {
        "id": p.id,
        "created_at": p.created_at,
        "content": p.content,
        "video_url": f"/media/{p.video_path}" if p.video_path else None,
        "ply_url": f"/media/{p.ply_path}" if p.ply_path else None,
        "traj_url": f"/media/{p.traj_path}" if p.traj_path else None,
        "points_url": f"/media/{p.points_path}" if p.points_path else None,
        "status": p.status,
        "log_url": (f"/media/{p.log_path}" if p.log_path else None),
        "store_name": p.author.store_name if p.author else None,
        "market": p.author.market if p.author else None,
        "stall_no": p.author.stall_no if p.author else None,
        "review_stats": _stats(db, p.id),
        "ai_summary": p.ai_summary,
        "products": _load_products_json_for_post(p),
    }

from fastapi import UploadFile as _UF, File as _File
@app.post("/posts", response_model=schemas.PostOut)
async def create_post_ply(
    ply: _UF = _File(...),
    traj: _UF | None = _File(None),
    coords: _UF | None = _File(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user_google),
):
    if user.role != "SELLER":
        raise HTTPException(status_code=403, detail="forbidden")

    ply_ext = Path(ply.filename).suffix.lower() or ".ply"
    ply_name = f"ply/{uuid.uuid4().hex}{ply_ext}"
    with open(media_root / ply_name, "wb") as f:
        while True:
            chunk = await ply.read(1024 * 1024)
            if not chunk: break
            f.write(chunk)
    await ply.close()

    traj_name = None
    if traj and traj.filename:
        traj_ext = Path(traj.filename).suffix.lower() or ".txt"
        traj_name = f"traj/{uuid.uuid4().hex}{traj_ext}"
        with open(media_root / traj_name, "wb") as f:
            while True:
                c = await traj.read(1024 * 1024)
                if not c: break
                f.write(c)
        await traj.close()

    points_name = None
    if coords and coords.filename:
        pts_ext = Path(coords.filename).suffix.lower() or ".txt"
        points_name = f"points/{uuid.uuid4().hex}{pts_ext}"
        with open(media_root / points_name, "wb") as f:
            while True:
                c = await coords.read(1024 * 1024)
                if not c: break
                f.write(c)
        await coords.close()

    post = models.Post(
        author_id=user.id,
        ply_path=ply_name, traj_path=traj_name, points_path=points_name
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return _post_out(post, db)

def _safe_stem(original_filename: str) -> str:
    stem = Path(original_filename).stem
    stem = re.sub(r"[^0-9A-Za-z가-힣 _.\-]", "_", stem).strip().strip(".")
    stem = re.sub(r"\s+", "_", stem)
    if not stem:
        stem = f"video_{uuid.uuid4().hex[:8]}"
    base = stem
    i = 2
    while (media_root / stem).exists():
        stem = f"{base}-{i}"
        i += 1
    return stem

def _append_log(log_file: Path, msg: str):
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"{datetime.utcnow().isoformat()}Z | {msg}\n")

def _classify_txt_name(name: str) -> str:
    n = name.lower()
    if any(k in n for k in ("traj", "trajectory", "tum")):
        return "traj"
    if any(k in n for k in ("point", "coord", "xyz")):
        return "points"
    return "traj"

def _process_video_job(post_id: int, video_rel: str, log_rel: str):
    log_file = media_root / log_rel
    _append_log(log_file, f"Job start post_id={post_id} video={video_rel}")
    db = SessionLocal()
    try:
        from . import process_video as pv
    except Exception as e:
        _append_log(log_file, f"process_video import 실패: {e}")
        db_post = db.query(models.Post).get(post_id)
        if db_post:
            db_post.status = "error"
            db.commit()
        db.close()
        return

    try:
        db_post = db.query(models.Post).get(post_id)
        if not db_post:
            _append_log(log_file, "Post not found")
            return

        db_post.status = "processing"
        db.commit()

        video_abs = media_root / video_rel
        work_dir = video_abs.parent

        _append_log(log_file, "3D 변환 시작(get_3d_model)")
        pv.get_3d_model(str(video_abs))
        product_result = pv.analyze_products_in_video(str(video_abs))
        pv.save_product_frames(str(video_abs), product_result)
        _append_log(log_file, "3D 변환 완료, 결과 스캔")

        ply_file = None
        txt_files = []
        json_files = []
        for pth in work_dir.iterdir():
            if pth.is_file():
                if pth.suffix.lower() == ".ply" and not ply_file:
                    ply_file = pth
                if pth.suffix.lower() == ".txt":
                    txt_files.append(pth)
                if pth.suffix.lower() == ".json":
                    json_files.append(pth)

        if not ply_file and not txt_files and not json_files:
            _append_log(log_file, "결과 파일(.ply/.txt/.json) 미발견")
            db_post.status = "error"
            db.commit()
            return

        if ply_file:
            rel = f"{work_dir.name}/{ply_file.name}"
            db_post.ply_path = rel
            _append_log(log_file, f"PLY 기록: /media/{rel}")

        used_traj = False
        used_points = False
        for t in txt_files:
            kind = _classify_txt_name(t.name)
            rel = f"{work_dir.name}/{t.name}"
            if kind == "traj" and not used_traj:
                db_post.traj_path = rel
                used_traj = True
                _append_log(log_file, f"TRAJ 기록: /media/{rel}")
            elif kind == "points" and not used_points:
                db_post.points_path = rel
                used_points = True
                _append_log(log_file, f"POINTS 기록(txt): /media/{rel}")
            else:
                _append_log(log_file, f"EXTRA TXT: /media/{rel}")

        # 좌표 포함된 제품 JSON을 points 소스로도 사용
        stem = work_dir.name
        target_json = None
        for j in json_files:
            if j.name.lower() == f"{stem}.json":
                target_json = j
                break
        if target_json is None and json_files:
            target_json = json_files[0]

        for j in json_files:
            _append_log(log_file, f"PRODUCTS JSON 발견: /media/{work_dir.name}/{j.name}")

        if target_json is not None:
            rel = f"{work_dir.name}/{target_json.name}"
            db_post.points_path = rel  # JSON 우선 사용 (PLYViewer가 x,y,z 추출)
            _append_log(log_file, f"COORDS(JSON) 기록: /media/{rel}")

        db_post.status = "done"
        db.commit()
        _append_log(log_file, "Job done")
    except Exception as e:
        _append_log(log_file, f"오류: {e}")
        _append_log(log_file, f"TRACE:\n{traceback.format_exc()}")
        try:
            db_post = db.query(models.Post).get(post_id)
            if db_post:
                db_post.status = "error"
                db.commit()
        except:
            pass
    finally:
        db.close()

@app.post("/posts/video", response_model=schemas.PostOut)
async def create_post_video(
    background: BackgroundTasks,
    video: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user_google),
):
    if user.role != "SELLER":
        raise HTTPException(status_code=403, detail="forbidden")

    ext = Path(video.filename).suffix.lower()
    if ext not in (".mp4",):
        raise HTTPException(status_code=400, detail="mp4_only")

    stem = _safe_stem(video.filename)
    work_dir = media_root / stem
    work_dir.mkdir(parents=True, exist_ok=True)

    video_rel = f"{stem}/{stem}{ext}"
    video_abs = media_root / video_rel

    with open(video_abs, "wb") as f:
        while True:
            chunk = await video.read(1024 * 1024)
            if not chunk: break
            f.write(chunk)
    await video.close()

    log_rel = f"{stem}/process.log"

    post = models.Post(
        author_id=user.id,
        video_path=video_rel,
        status="processing",
        log_path=log_rel,
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    background.add_task(_process_video_job, post.id, video_rel, log_rel)

    return _post_out(post, db)

@app.get("/posts", response_model=list[schemas.PostOut])
def list_posts(db: Session = Depends(get_db)):
    posts = db.query(models.Post).order_by(models.Post.id.desc()).all()
    return [_post_out(p, db) for p in posts]

@app.get("/posts/{post_id}", response_model=schemas.PostOut)
def get_post(post_id: int, db: Session = Depends(get_db)):
    p = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="not_found")
    return _post_out(p, db)

@contextmanager
def _snowflake_conn():
    try:
        import snowflake.connector as sf
    except Exception as e:
        logger.error("Snowflake 커넥터 import 실패: %s", e)
        raise
    cfg = {
        "account":   settings.snowflake_account,
        "user":      settings.snowflake_user,
        "password":  settings.snowflake_password,
        "role":      settings.snowflake_role,
        "warehouse": settings.snowflake_warehouse,
        "database":  settings.snowflake_database,
        "schema":    settings.snowflake_schema,
        "client_session_keep_alive": True,
    }
    redacted = {k: ("***" if k == "password" else v) for k, v in cfg.items()}
    _log_kv("Snowflake 연결 시도", **redacted)

    for k in ("account","user","password","warehouse","database","schema"):
        if not cfg.get(k):
            raise RuntimeError(f"Snowflake 설정 누락: {k}")

    conn = None
    try:
        conn = sf.connect(**cfg)
        cur = conn.cursor()
        try:
            cur.execute("SELECT CURRENT_ROLE(), CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_SCHEMA()")
            row = cur.fetchone()
            _log_kv("Snowflake 세션 확인",
                    current_role=row[0], current_wh=row[1], current_db=row[2], current_schema=row[3])
        finally:
            cur.close()
        yield conn
    except Exception as e:
        logger.error("Snowflake 연결 실패: %s", e)
        logger.error("TRACE:\n%s", traceback.format_exc())
        raise
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass

def _snowflake_cortex_complete(conn, prompt: str, model_list: Optional[list[str]] = None) -> str:
    if model_list is None:
        model_list = [
            "mistral-large2",
            "mistral-large",
            "snowflake-arctic",
            "snowflake-arctic-m",
            "llama3-70b-instruct",
        ]
    _log_kv("Cortex 호출 준비", prompt_preview=prompt[:160].replace("\n", " "))
    def esc(s: str) -> str:
        return s.replace("'", "''")
    cur = conn.cursor()
    try:
        for model in model_list:
            try:
                sql = f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{esc(model)}', '{esc(prompt)}') AS TEXT"
                _log_kv("Cortex 시도", model=model)
                cur.execute(sql)
                row = cur.fetchone()
                if row and row[0] is not None:
                    text = str(row[0])
                    _log_kv("Cortex 성공", model=model, len=len(text))
                    return text
            except Exception as e:
                logger.warning("모델 %s 실패: %s", model, e)
        raise RuntimeError("모든 Cortex 모델 호출 실패")
    finally:
        cur.close()

def _build_shop_prompt(store_name: str, market: Optional[str], stall_no: Optional[str], stats: schemas.ReviewStats) -> str:
    def part(tag: str, d: dict) -> str:
        kv = ", ".join(f"{k}:{v}" for k, v in d.items())
        return f"{tag}({kv})"
    reviews = f"총 {stats.total}명이 평가. " \
              f"{part('친절도', stats.kindness)}, " \
              f"{part('가격',   stats.price)}, " \
              f"{part('구성',   stats.variety)}."
    loc = []
    if market: loc.append(f"시장: {market}")
    if stall_no: loc.append(f"위치/호수: {stall_no}")
    loc_str = " / ".join(loc) if loc else "위치 정보: 미상"
    guide = (
    "아래 가게에 대한 한국어 소개문을 작성하세요.\n"
    "- 길이: 300자 이상 600자 이하, 3~6문장.\n"
    "- 톤: 밝고 따뜻하며 먹음직스럽게. 과장·허위·이모지 금지.\n"
    "- 가능한 한 리뷰 요약을 근거로 인상과 장점을 균형 있게 서술.\n"
    "- 특정 고유명사는 그대로 유지.\n"
    "- **시장 주변의 명소**를 활용하여, 가게 방문 동선을 자연스럽게 연결해 소개.\n"
    "- **시장을 제외한 구체적인 명소 이름을 찾아오고, 없으면 생략. 단, 반드시 동대문구 안에 있는 장소여야 함.\n"
    "- 주변 명소는 *도보 n분*이나 *차로 m분*과 같은 형식으로 서술. 모호하면 “가까운”, “근처” 등 일반 표현 사용.\n"
    "- 눈길을 끌 수 있는 센스 있는 문구를 적절히 포함.\n"
    "- **반드시 Markdown 문법을 적극적으로 활용**하여 시장, 평가, 주변 명소를 적절히 강조할 것.\n"
    "- 마지막 줄에는 한 줄 띄운 후, 파란 글씨(`span` 태그 style)로 적절한 해시태그를 넣을 것.\n"
    "- 오직 소개문만 출력하고, 추가 설명은 하지 말 것.\n"
)
    info = (
        f"[가게명] {store_name or '이 가게'}\n"
        f"[시장/위치] {loc_str}\n"
        f"[리뷰 요약] {reviews}\n"
    )
    return guide + "\n" + info + "\n[출력형식] 순수 본문만 작성"

@app.get("/posts/{post_id}/summary", response_model=schemas.PostOut)
def get_post_for_summary(post_id: int, db: Session = Depends(get_db)):
    p = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="not_found")
    return _post_out(p, db)

@app.post("/posts/{post_id}/summary", response_model=dict)
def gen_summary(post_id: int, db: Session = Depends(get_db)):
    p = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="not_found")

    store_name = p.author.store_name if p.author else None
    market = p.author.market if p.author else None
    stall_no = p.author.stall_no if p.author else None
    stats = _stats(db, post_id)

    _log_kv("요약생성 시작", post_id=post_id, store_name=store_name, market=market, stall_no=stall_no, reviews_total=stats.total)

    prompt = _build_shop_prompt(store_name, market, stall_no, stats)
    text: Optional[str] = None
    try:
        with _snowflake_conn() as conn:
            text = _snowflake_cortex_complete(conn, prompt)
    except Exception as e:
        logger.error("Snowflake 호출 실패: %s", e)
        logger.error("TRACE:\n%s", traceback.format_exc())
        if not p.ai_summary:
            lines = [f"{store_name or '이 가게'}은(는) 지역 시장에서 사랑받는 곳입니다."]
            if stats.total:
                if stats.kindness.get("pos", 0) >= stats.kindness.get("neg", 0):
                    lines.append("친절한 응대로 손님을 맞이합니다.")
                if stats.price.get("cheap", 0) >= stats.price.get("exp", 0):
                    lines.append("가격대도 합리적이에요.")
                if stats.variety.get("div", 0) >= stats.variety.get("low", 0):
                    lines.append("메뉴/상품 구성이 다양해 선택의 폭이 넓어요.")
            text = " ".join(lines)
            _log_kv("폴백 소개문 사용", length=len(text))

    if text is None:
        raise HTTPException(status_code=502, detail="summary_generation_failed")

    try:
        p.ai_summary = text
        db.commit()
        _log_kv("소개문 저장 완료", post_id=post_id, length=len(text))
    except Exception as e:
        logger.error("소개문 저장 실패: %s", e)
        logger.error("TRACE:\n%s", traceback.format_exc())

    return {"ok": True, "text": text, "ai_summary": text}
