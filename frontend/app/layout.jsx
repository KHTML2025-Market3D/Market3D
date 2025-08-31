"use client";
import { SessionProvider } from "next-auth/react";
import Header from "./components/header.jsx";

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        {/* 고정 파스텔 배경 */}
        <div className="AppBackground" aria-hidden />

        <SessionProvider refetchOnWindowFocus={false} refetchInterval={0}>
          {/* 콘텐츠가 배경 위에 올라오도록 스택 분리 */}
          <div className="AppRoot">
            <Header />
            {children}
          </div>
        </SessionProvider>

        <style jsx global>{`
          :root{
            --bg-a:#e7f0ff; /* 파스텔 블루 */
            --bg-b:#ffe1ea; /* 파스텔 핑크 */
            --bg-c:#e9fff3; /* 파스텔 민트 */
            --bg-d:#ffeccf; /* 파스텔 피치 */
          }

          html, body { min-height:100%; }
          /* 다른 곳에서 body 배경을 하양으로 덮어써도 보이게 투명 처리 */
          body { background: transparent !important; }

          /* 페이지 컨테이너가 자체 배경을 갖고 있으면 투명하게 */
          .Page { background: transparent; }

          /* 뷰포트를 꽉 채우는 고정 배경 레이어 */
          .AppBackground{
            position: fixed;
            inset: 0;
            z-index: 0;
            pointer-events: none;
            background:
              radial-gradient(1100px 650px at -10% 0%, var(--bg-a) 0%, transparent 66%),
              radial-gradient(1100px 650px at 110% -5%, var(--bg-b) 0%, transparent 66%),
              radial-gradient(1100px 750px at -5% 105%, var(--bg-c) 0%, transparent 70%),
              radial-gradient(950px 680px at 105% 105%, var(--bg-d) 0%, transparent 70%),
              linear-gradient(180deg, #f3f7ff 0%, #fff1e6 100%);
            background-attachment: fixed, fixed, fixed, fixed, fixed;
          }

          /* 실제 콘텐츠는 배경 위로 */
          .AppRoot{
            position: relative;
            z-index: 1;
          }
        `}</style>
      </body>
    </html>
  );
}
