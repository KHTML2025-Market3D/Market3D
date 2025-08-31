"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import "./page.css";

const BURL = process.env.NEXT_PUBLIC_BACKEND_URL;

export default function Home() {
  const [state, setState] = useState({
    loading: true,
    error: null,
    posts: [],
  });
  const [q, setQ] = useState("");

  useEffect(() => {
    const run = async () => {
      if (!BURL) console.warn("NEXT_PUBLIC_BACKEND_URL is not defined");
      try {
        const res = await fetch(`${BURL}/posts`, {
          cache: "no-store",
          headers: { Accept: "application/json" },
        });
        if (!res.ok) {
          const text = await res.text().catch(() => "");
          throw new Error(`GET /posts ${res.status} ${text?.slice(0, 200)}`);
        }
        const data = await res.json();
        if (!Array.isArray(data)) {
          setState({
            loading: false,
            error: "목록 응답 형식이 올바르지 않습니다.",
            posts: [],
          });
          return;
        }
        setState({ loading: false, error: null, posts: data });
      } catch (err) {
        console.error("Failed to fetch /posts:", err);
        setState({
          loading: false,
          error: "목록을 불러오지 못했습니다. 서버가 켜져 있는지 확인하세요.",
          posts: [],
        });
      }
    };
    run();
  }, []);

  const { loading, error, posts } = state;

  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    if (!term) return posts;
    return posts.filter((p) => {
      const store = (p?.store_name ?? "").toLowerCase();
      const market = (p?.market ?? "").toLowerCase();
      const summary = (p?.ai_summary ?? "").toLowerCase();
      return (
        store.includes(term) ||
        market.includes(term) ||
        summary.includes(term)
      );
    });
  }, [posts, q]);

  return (
    <main className="Page">
      <div className="Toolbar">
        <h1 className="Title">게시글</h1>
        <Link href="/posts/new" className="NewBtn">
          새 글
        </Link>
      </div>

      <div className="SearchBar">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="상점명 · 시장명 · 소개문으로 검색"
          className="SearchInput"
          type="search"
        />
        {q && (
          <button className="ClearBtn" onClick={() => setQ("")} aria-label="검색어 지우기">
            ×
          </button>
        )}
      </div>

      {loading && <p className="Hint">불러오는 중…</p>}
      {error && <p className="Error">{error}</p>}
      {!loading && !error && filtered.length === 0 && (
        <p className="Hint">검색 결과가 없습니다.</p>
      )}

      <ul className="Grid">
        {filtered.map((p) => {
          const created = p?.created_at ? new Date(p.created_at).toLocaleString() : "";
          const title = p?.store_name || `#${p?.id}`;
          const sub = [p?.market, p?.stall_no].filter(Boolean).join(" · ");
          const preview =
            (p?.ai_summary || p?.content || "").replace(/\s+/g, " ").slice(0, 140);

          return (
            <li key={p.id ?? Math.random()} className="Card">
              <Link href={`/posts/${p.id}`} className="CardLink">
                <div className="CardHead">
                  <div className="CardTitle">{title}</div>
                  <div className="CardMeta">{created}</div>
                </div>
                {!!sub && <div className="CardSub">{sub}</div>}
                {!!preview && <div className="CardBody">{preview}</div>}
              </Link>
            </li>
          );
        })}
      </ul>
    </main>
  );
}
