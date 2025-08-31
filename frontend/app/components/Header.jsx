"use client";
import { useEffect, useState } from "react";
import { useSession, signOut } from "next-auth/react";
import { useRouter } from "next/navigation";

const BURL = process.env.NEXT_PUBLIC_BACKEND_URL;

export default function Header() {
  const { data: session, status } = useSession();
  const idToken = session?.id_token;
  const [me, setMe] = useState(null);
  const router = useRouter();

  useEffect(() => {
    let aborted = false;
    const run = async () => {
      if (!idToken) { setMe(null); return; }
      try {
        const r = await fetch(`${BURL}/me`, {
          headers: { Authorization: `Bearer ${idToken}` },
          cache: "no-store",
        });
        if (!aborted) setMe(r.ok ? await r.json() : null);
      } catch {
        if (!aborted) setMe(null);
      }
    };
    run();
    return () => { aborted = true; };
  }, [idToken]);

  const brandText =
    me?.name ||
    me?.display_name ||
    session?.user?.name ||
    "동동동동동대문을열어라사후르";

  return (
    <header className="hdr">
      <a href="/" className="brand" title={brandText}>{brandText}</a>
      <div className="spacer" />
      {me?.role === "SELLER" && (
        <div className="seller">
          {me.market ? `[${me.market}] ` : ""}{me.store_name || "상호미등록"}{me.stall_no ? ` (${me.stall_no})` : ""}
        </div>
      )}
      {status === "authenticated" ? (
        <button className="btn" onClick={() => signOut()}>로그아웃</button>
      ) : (
        <button className="btn primary" onClick={() => router.push("/login")}>로그인</button>
      )}

      <style jsx>{`
        .hdr {
          position: sticky;
          top: 0;
          z-index: 50;
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 10px 16px;
          backdrop-filter: blur(6px);
          -webkit-backdrop-filter: blur(6px);
          background: linear-gradient(180deg, rgba(255,255,255,0.75), rgba(255,255,255,0.6));
          border-bottom: 1px solid rgba(0,0,0,0.06);
          box-shadow: 0 1px 6px rgba(0,0,0,0.04);
        }
        @media (prefers-color-scheme: dark) {
          .hdr {
            background: linear-gradient(180deg, rgba(20,20,20,0.7), rgba(20,20,20,0.55));
            border-bottom-color: rgba(255,255,255,0.08);
            box-shadow: 0 1px 8px rgba(0,0,0,0.4);
          }
        }
        .brand {
          font-weight: 800;
          font-size: 18px;
          text-decoration: none;
          background: linear-gradient(90deg, #4f46e5, #06b6d4);
          -webkit-background-clip: text;
          background-clip: text;
          color: transparent;
          max-width: 40vw;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .brand:hover { opacity: 0.9; }
        .spacer { flex: 1; }
        .seller {
          font-size: 13px;
          color: #555;
          white-space: nowrap;
        }
        @media (prefers-color-scheme: dark) {
          .seller { color: #cfcfcf; }
        }
        .btn {
          appearance: none;
          border: 1px solid rgba(0,0,0,0.12);
          background: #fff;
          padding: 6px 12px;
          font-size: 14px;
          border-radius: 9999px;
          cursor: pointer;
          transition: transform .08s ease, box-shadow .12s ease, background .2s ease, border-color .2s ease;
        }
        .btn:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.08); transform: translateY(-1px); }
        .btn:active { transform: translateY(0); }
        .btn.primary {
          border-color: transparent;
          background: linear-gradient(90deg, #4f46e5, #06b6d4);
          color: white;
        }
        @media (prefers-color-scheme: dark) {
          .btn { background: #1f1f1f; border-color: rgba(255,255,255,0.14); color: #efefef; }
          .btn.primary { background: linear-gradient(90deg, #6366f1, #22d3ee); }
        }
      `}</style>
    </header>
  );
}
