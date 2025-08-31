"use client";
import { useSession } from "next-auth/react";
import { useEffect, useRef, useState } from "react";

const BURL = process.env.NEXT_PUBLIC_BACKEND_URL;

export default function NewPostPage() {
  const { status, data } = useSession();
  const idt = data?.id_token;

  const [video, setVideo] = useState(null);
  const [busy, setBusy] = useState(false);
  const [logText, setLogText] = useState("");
  const [postId, setPostId] = useState(null);
  const [statusText, setStatusText] = useState(null);
  const [logUrl, setLogUrl] = useState(null);
  const pollRef = useRef(null);
  const logRef = useRef(null);

  useEffect(() => {
    if (!postId) return;
    const poll = async () => {
      try {
        const r = await fetch(`${BURL}/posts/${postId}`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const j = await r.json();
        setStatusText(j?.status || null);
        if (!logUrl && j?.log_url) setLogUrl(`${BURL}${j.log_url}`);
        if (j?.status === "done") {
          clearInterval(pollRef.current);
          clearInterval(logRef.current);
          window.location.replace(`/posts/${j.id}`);
        }
        if (j?.status === "error") {
          clearInterval(pollRef.current);
          clearInterval(logRef.current);
          setBusy(false);
          alert("처리 중 오류가 발생했습니다. 로그를 확인하세요.");
        }
      } catch (e) {
        // 무시하고 다음 주기 재시도
      }
    };
    const fetchLog = async () => {
      try {
        if (!logUrl) return;
        const r = await fetch(logUrl, { cache: "no-store" });
        if (r.ok) {
          const t = await r.text();
          setLogText(t);
        }
      } catch {}
    };
    poll(); fetchLog();
    pollRef.current = setInterval(poll, 7000);
    logRef.current  = setInterval(fetchLog, 5000);
    return () => {
      clearInterval(pollRef.current);
      clearInterval(logRef.current);
    };
  }, [postId, logUrl]);

  if (status === "loading")
    return (
      <main style={{maxWidth:720,margin:"40px auto",padding:16}}>
        <h1>영상 업로드</h1>
        <p>세션 확인중…</p>
      </main>
    );

  if (status !== "authenticated")
    return (
      <main style={{maxWidth:720,margin:"40px auto",padding:16}}>
        <h1>영상 업로드</h1>
        <p>로그인이 필요합니다</p>
      </main>
    );

  const submit = async (e) => {
    e.preventDefault();
    if (!video) return alert("MP4 파일을 선택하세요.");
    setBusy(true);
    setLogText("업로드 시작…");
    setStatusText("processing");
    try {
      const fd = new FormData();
      fd.append("video", video);
      const r = await fetch(`${BURL}/posts/video`, {
        method: "POST",
        headers: { Authorization: `Bearer ${idt}` },
        body: fd,
      });
      const text = await r.text();
      if (!r.ok) throw new Error(text || `HTTP ${r.status}`);
      const j = JSON.parse(text || "{}");
      setPostId(j?.id);
      if (j?.log_url) setLogUrl(`${BURL}${j.log_url}`);
      setLogText((prev) => prev + "\n서버 처리 대기/진행 중…");
    } catch (err) {
      setBusy(false);
      setStatusText(null);
      alert(`등록 실패: ${err.message}`);
    }
  };

  return (
    <main style={{ maxWidth:720, margin:"40px auto", padding:16, display:"grid", gap:12 }}>
      <h1>영상 업로드 (MP4)</h1>
      <form onSubmit={submit} style={{ display:"grid", gap:12 }}>
        <label>동영상 파일(.mp4)</label>
        <input
          type="file"
          accept="video/mp4"
          onChange={(e)=>setVideo(e.target.files?.[0]||null)}
          required
        />
        <button type="submit" disabled={busy}>
          {busy ? (statusText === "processing" ? "처리 중…" : "업로드 중…") : "등록"}
        </button>
      </form>
      {!!postId && (
        <div style={{marginTop:8, fontSize:14, opacity:.85}}>
          <div>Post ID: {postId}</div>
          <div>상태: {statusText || "-"}</div>
        </div>
      )}
      {logUrl && (
        <details open>
          <summary style={{cursor:"pointer"}}>실시간 로그 (자동 새로고침)</summary>
          <pre style={{whiteSpace:"pre-wrap",opacity:.85,marginTop:8, maxHeight:360, overflow:"auto"}}>
            {logText || "로그 수집 중…"}
          </pre>
        </details>
      )}
    </main>
  );
}
