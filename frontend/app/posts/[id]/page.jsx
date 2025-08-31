"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import dynamic from "next/dynamic";
import "./page.css";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";

const BURL = process.env.NEXT_PUBLIC_BACKEND_URL;
const PlyViewer = dynamic(() => import("../../components/PLYViewer.jsx"), { ssr: false });
const ReactMarkdown = dynamic(() => import("react-markdown").then(m => m.default), { ssr: false });

const toInt = (v) => (v === "1" ? 1 : v === "-1" ? -1 : 0);

function StatLine({ label, data }) {
  if (!data) return null;
  const pos = Number(data["1"] ?? data.pos ?? data.positive ?? 0);
  const neu = Number(data["0"] ?? data.neu ?? data.neutral ?? 0);
  const neg = Number(data["-1"] ?? data.neg ?? data.negative ?? 0);
  const total = pos + neu + neg;
  if (total > 0) {
    const p = Math.round((pos / total) * 100);
    const n = Math.round((neu / total) * 100);
    const g = Math.round((neg / total) * 100);
    return (
      <div style={{ display: "grid", gridTemplateColumns: "90px 1fr auto", gap: 8, alignItems: "center" }}>
        <div style={{ color: "#555" }}>{label}</div>
        <div style={{ height: 8, background: "#eef2ff", borderRadius: 999, overflow: "hidden" }}>
          <div style={{ width: `${p}%`, height: "100%", background: "#22c55e", float: "left" }} />
          <div style={{ width: `${n}%`, height: "100%", background: "#94a3b8", float: "left" }} />
          <div style={{ width: `${g}%`, height: "100%", background: "#ef4444", float: "left" }} />
        </div>
        <div style={{ fontVariantNumeric: "tabular-nums", color: "#666" }}>{p}% / {n}% / {g}%</div>
      </div>
    );
  }
  const avg = Number(data.avg ?? data.mean ?? data);
  if (!Number.isNaN(avg) && avg !== 0) {
    const pct = Math.round(((avg + 1) / 2) * 100);
    return (
      <div style={{ display: "grid", gridTemplateColumns: "90px 1fr auto", gap: 8, alignItems: "center" }}>
        <div style={{ color: "#555" }}>{label}</div>
        <div style={{ height: 8, background: "#eef2ff", borderRadius: 999, overflow: "hidden" }}>
          <div style={{ width: `${pct}%`, height: "100%", background: "#4f46e5" }} />
        </div>
        <div style={{ fontVariantNumeric: "tabular-nums", color: "#666" }}>{pct}%</div>
      </div>
    );
  }
  return (
    <div style={{ display: "grid", gridTemplateColumns: "90px 1fr", gap: 8 }}>
      <div style={{ color: "#555" }}>{label}</div>
      <div style={{ color: "#888" }}>아직 데이터 없음</div>
    </div>
  );
}

export default function PostDetail({ params }) {
  const { id } = params;
  const { data: session } = useSession();
  const idToken = session?.id_token;

  const [me, setMe] = useState(null);
  const [post, setPost] = useState(null);
  const [saving, setSaving] = useState(false);
  const [note, setNote] = useState("");
  const [genNote, setGenNote] = useState("");
  const [form, setForm] = useState({ kindness: 0, price: 0, variety: 0 });
  const [hovered, setHovered] = useState(-1);

  useEffect(() => {
    const init = async () => {
      if (idToken) {
        try {
          const r = await fetch(`${BURL}/me`, { headers: { Authorization: `Bearer ${idToken}` } });
          setMe(r.ok ? await r.json() : null);
        } catch { setMe(null); }
      } else { setMe(null); }

      const rp = await fetch(`${BURL}/posts/${id}`, { cache: "no-store" });
      if (rp.ok) setPost(await rp.json());
    };
    init();
  }, [id, idToken]);

  const saveReview = async () => {
    if (!idToken) return setNote("로그인 후 이용해주세요.");
    if (me?.role !== "BUYER") return setNote("구매자만 평가할 수 있어요.");
    try {
      setSaving(true);
      const r = await fetch(`${BURL}/posts/${id}/reviews`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${idToken}` },
        body: JSON.stringify(form),
      });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(e.detail || "save_failed");
      }
      const stats = await r.json();
      setPost((p) => ({ ...p, review_stats: stats }));
      setNote("저장했어요!");
    } catch (e) {
      setNote(`에러: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const genSummary = async () => {
    try {
      setGenNote("소개문 생성 중…");
      const r = await fetch(`${BURL}/posts/${id}/summary`, { method: "POST" });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(e.detail || "gen_failed");
      }
      const data = await r.json();
      const summary = data.text ?? data.ai_summary ?? data.summary ?? data.message ?? "";
      setPost((p) => ({ ...p, ai_summary: summary }));
      setGenNote(summary ? "완료!" : "완료 — 내용 없음");
    } catch (e) {
      setGenNote(`에러: ${e.message}`);
    }
  };

  if (!post) return <div style={{ padding: 16 }}>로딩중…</div>;

  const plyUrl = post.ply_url ? `${BURL}${post.ply_url}` : null;
  const trajUrl = post.traj_url ? `${BURL}${post.traj_url}` : null;
  const pointsUrl = post.points_url ? `${BURL}${post.points_url}` : null;

  const isBuyer = me?.role === "BUYER";
  const stats = post?.review_stats ?? null;
  const products = Array.isArray(post?.products) ? post.products : [];

  const hoveredImageUrl = hovered >= 0 && products[hovered]?.image_url
    ? `${BURL}${products[hovered].image_url}`
    : null;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 380px", gap: 16 }}>
      <div>
        <section className="IntroCard">
          <div className="intro-head">
            <h4>가게 소개문</h4>
            <button onClick={genSummary}>{post.ai_summary ? "다시 생성" : "생성하기"}</button>
          </div>
          <div className="intro-status">{genNote}</div>
          <div className="intro-body md-body">
            {post.ai_summary ? (
              <ReactMarkdown
  remarkPlugins={[remarkGfm]}
  rehypePlugins={[rehypeRaw]}
  components={{
    a: ({node, ...props}) => (
      <a {...props} target="_blank" rel="noopener noreferrer" />
    ),
    img: ({node, ...props}) => <img {...props} loading="lazy" />
  }}
>
  {post.ai_summary}
</ReactMarkdown>

            ) : (
              "아직 생성된 소개문이 없습니다. '생성하기'를 눌러 보세요."
            )}
          </div>
        </section>

        <div style={{ minHeight: "70vh", marginTop: 16 }}>
          <PlyViewer plyUrl={plyUrl} trajUrl={trajUrl} pointsUrl={pointsUrl} height="78vh" />
        </div>
      </div>

      <aside style={{ padding: 12 }}>
        <h3 style={{ marginBottom: 6 }}>{post.store_name || "가게"}</h3>
        <div style={{ color: "#666", marginBottom: 12 }}>
          {post.market ? `[${post.market}] ` : ""}{post.stall_no || ""}
        </div>

        <div className="ProductsCard">
          <div className="products-head">
            <h4>상품 목록</h4>
          </div>

          <div className="products-preview">
            {hoveredImageUrl ? (
              <img src={hoveredImageUrl} alt="상품 미리보기" />
            ) : (
              <div className="preview-empty">품목에 마우스를 올리면 이미지가 보여요</div>
            )}
          </div>

          <div className="products-body">
            {products.length ? (
              <ul className="products-list">
                {products.map((p, i) => {
                  const t = `${p.time_min ?? 0}:${String(p.time_sec ?? 0).padStart(2,"0")}.${String(p.time_ms ?? 0).padStart(3,"0")}`;
                  const hasImg = !!p.image_url;
                  return (
                    <li
                      key={i}
                      className={`ProductItem${hovered===i ? " is-hover" : ""}${hasImg ? " has-img" : ""}`}
                      onMouseEnter={() => setHovered(i)}
                      onMouseLeave={() => setHovered(-1)}
                    >
                      <div className="pi-left">
                        <div className="pi-name">{p.name || "상품"}</div>
                        <div className="pi-time">{t}</div>
                      </div>
                      <div className="pi-right">{p.price ?? "-"}</div>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <div className="products-empty">표시할 상품 데이터가 없습니다.</div>
            )}
          </div>
        </div>

        <div style={{ display: "grid", gap: 10, background: "var(--ig-card)", border: "1px solid var(--ig-border)", borderRadius: 16, padding: 12 }}>
          <h4 style={{ margin: 0 }}>구매자 평가 통계</h4>
          {stats ? (
            <>
              <StatLine label="친절도" data={stats.kindness_counts ?? stats.kindness} />
              <StatLine label="가격"   data={stats.price_counts ?? stats.price} />
              <StatLine label="다양성" data={stats.variety_counts ?? stats.variety} />
              <div style={{ color:"#777" }}>총 참여: {Number(stats.total ?? stats.count ?? stats.n ?? 0)}명</div>
            </>
          ) : (
            <div style={{ color:"#777" }}>아직 평가 통계가 없습니다.</div>
          )}
        </div>

        {isBuyer && (
          <>
            <hr style={{ margin: "16px 0" }} />
            <h4>구매자 평가</h4>
            <div style={{ marginTop: 8 }}>
              <div style={{ marginBottom: 8 }}>
                <div>친절도</div>
                <label><input type="radio" name="kindness" value="1"   onChange={(e)=>setForm(f=>({...f, kindness: toInt(e.target.value)}))}/> 친절</label>{" "}
                <label><input type="radio" name="kindness" value="0"   defaultChecked onChange={(e)=>setForm(f=>({...f, kindness: toInt(e.target.value)}))}/> 보통</label>{" "}
                <label><input type="radio" name="kindness" value="-1"  onChange={(e)=>setForm(f=>({...f, kindness: toInt(e.target.value)}))}/> 불친절</label>
              </div>

              <div style={{ marginBottom: 8 }}>
                <div>가격</div>
                <label><input type="radio" name="price" value="1"   onChange={(e)=>setForm(f=>({...f, price: toInt(e.target.value)}))}/> 저렴</label>{" "}
                <label><input type="radio" name="price" value="0"   defaultChecked onChange={(e)=>setForm(f=>({...f, price: toInt(e.target.value)}))}/> 보통</label>{" "}
                <label><input type="radio" name="price" value="-1"  onChange={(e)=>setForm(f=>({...f, price: toInt(e.target.value)}))}/> 비쌈</label>
              </div>

              <div style={{ marginBottom: 8 }}>
                <div>다양성</div>
                <label><input type="radio" name="variety" value="1"   onChange={(e)=>setForm(f=>({...f, variety: toInt(e.target.value)}))}/> 다양</label>{" "}
                <label><input type="radio" name="variety" value="0"   defaultChecked onChange={(e)=>setForm(f=>({...f, variety: toInt(e.target.value)}))}/> 보통</label>{" "}
                <label><input type="radio" name="variety" value="-1"  onChange={(e)=>setForm(f=>({...f, variety: toInt(e.target.value)}))}/> 적음</label>
              </div>

              <button
                onClick={saveReview}
                disabled={saving || !(me && me.role === "BUYER")}
                style={{ padding: "8px 12px", borderRadius: 6, border: "1px solid #111", background:"#111", color:"#fff" }}
              >
                {saving ? "저장중…" : "평가 저장"}
              </button>
              <div style={{ marginTop: 8, color: "#777" }}>{note}</div>
            </div>
          </>
        )}
      </aside>
    </div>
  );
}
