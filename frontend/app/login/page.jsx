"use client";
import { signIn } from "next-auth/react";
import "./page.css";

export default function LoginPage() {
  const toGoogle = () => signIn("google", { callbackUrl: "/onboard" });

  return (
    <main className="Login">
      <section className="Card" aria-labelledby="login-title">
        <header className="Header">
          <div className="Mark" aria-hidden="true">🌼</div>
          <h1 id="login-title" className="Title">로그인</h1>
          <p className="Sub">구글 계정으로 바로 시작해요.</p>
        </header>

        <div className="Actions">
          <button className="GoogleBtn" onClick={toGoogle} aria-label="구글로 로그인">
            <span className="GIcon" aria-hidden="true">
              <svg width="24" height="24" viewBox="0 0 533.5 544.3">
                <path fill="#EA4335" d="M533.5 278.4c0-17.4-1.6-34.1-4.7-50.2H272v95.1h146.9c-6.3 34.1-25.3 63-54 82.4v68h87.3c51-47 81.3-116.1 81.3-195.3z"/>
                <path fill="#34A853" d="M272 544.3c73.5 0 135.2-24.3 180.3-66.1l-87.3-68c-24.2 16.2-55.2 25.6-93 25.6-71.5 0-132.1-48.3-153.8-113.3H28.6v70.9C73.5 489.4 166.7 544.3 272 544.3z"/>
                <path fill="#4A90E2" d="M118.2 322.5c-10.1-30.1-10.1-63.1 0-93.2V158.4H28.6c-39.6 79.1-39.6 173.4 0 252.5l89.6-88.4z"/>
                <path fill="#FBBC05" d="M272 106.2c39.9-.6 78.2 14.3 107.6 41.9l80.3-80.3C407.3 21.9 344.8-.1 272 0 166.7 0 73.5 54.9 28.6 159.8l89.6 70.9C139.9 154.9 200.5 106.6 272 106.2z"/>
              </svg>
            </span>
            구글로 로그인
            <span className="Arrow" aria-hidden="true">→</span>
          </button>
        </div>
      </section>
    </main>
  );
}
