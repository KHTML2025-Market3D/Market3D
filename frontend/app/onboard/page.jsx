"use client";

import { useEffect, useState } from "react";
import { useSession, signIn } from "next-auth/react";

const BURL = process.env.NEXT_PUBLIC_BACKEND_URL;

export default function OnboardPage() {
  const { data: session, status } = useSession();
  const [role, setRole] = useState("BUYER");
  const [storeName, setStoreName] = useState("");
  const [market, setMarket] = useState("");
  const [stallNo, setStallNo] = useState("");
  const [markets, setMarkets] = useState([]);
  const [note, setNote] = useState("");

  const idToken = session?.id_token;

  useEffect(() => {
    // 시장 목록
    fetch(`${BURL}/markets`)
      .then((r) => r.json())
      .then(setMarkets)
      .catch(() => setMarkets([]));
  }, []);

  const onSubmit = async () => {
    if (!idToken) {
      setNote("구글 로그인 먼저 진행해주세요.");
      await signIn("google");
      return;
    }
    try {
      const payload = { id_token: idToken, role };
      if (role === "SELLER") {
        payload.store_name = storeName.trim();
        payload.market = market;
        payload.stall_no = stallNo.trim() || null;
      }
      const r = await fetch(`${BURL}/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(e.detail || "signup_failed");
      }
      setNote("완료! 메인으로 이동합니다.");
      window.location.href = "/";
    } catch (e) {
      setNote(`에러: ${e.message}`);
    }
  };

  // --- Styles ---
  const styles = {
    container: {
      maxWidth: 560,
      margin: "40px auto",
      padding: "24px",
      border: "1px solid #eee",
      borderRadius: 12,
      boxShadow: "0 4px 12px rgba(0,0,0,0.05)",
    },
    title: {
      marginBottom: 24,
      textAlign: "center",
      fontSize: "1.5rem",
      fontWeight: 600,
    },
    roleSelector: {
      display: "grid",
      gridTemplateColumns: "1fr 1fr",
      gap: 12,
      marginBottom: 28,
    },
    roleButton: (isSelected) => ({
      padding: "16px",
      border: isSelected ? "2px solid #111" : "1px solid #ddd",
      borderRadius: 8,
      textAlign: "center",
      cursor: "pointer",
      fontWeight: 500,
      backgroundColor: isSelected ? "#f9f9f9" : "#fff",
      transition: "all 0.2s",
    }),
    formSection: {
      display: "grid",
      gap: 20,
    },
    formField: {
      display: "grid",
      gap: 6,
    },
    label: {
      fontWeight: 500,
      fontSize: "0.9rem",
    },
    input: {
      display: "block",
      width: "100%",
      padding: "10px 12px",
      border: "1px solid #ccc",
      borderRadius: 6,
      fontSize: "1rem",
    },
    submitButton: {
      marginTop: 18,
      padding: "12px 18px",
      borderRadius: 8,
      border: "none",
      background: "#111",
      color: "#fff",
      fontSize: "1rem",
      fontWeight: 600,
      cursor: "pointer",
      width: "100%",
    },
    note: {
      marginTop: 16,
      color: "#777",
      textAlign: "center",
      minHeight: "1.2em",
    },
  };
  // --- Render ---
  return (
    <div style={styles.container}>
      <h2 style={styles.title}>회원 정보 설정</h2>

      <div style={styles.roleSelector}>
        <div style={styles.roleButton(role === "BUYER")} onClick={() => setRole("BUYER")}>
          구매자
        </div>
        <div style={styles.roleButton(role === "SELLER")} onClick={() => setRole("SELLER")}>
          판매자
        </div>
      </div>

      {role === "SELLER" && (
        <div style={styles.formSection}>
          <div style={styles.formField}>
            <label style={styles.label}>가게 이름</label>
            <input
              type="text"
              value={storeName}
              onChange={(e) => setStoreName(e.target.value)}
              placeholder="예) 행복슈퍼"
              style={styles.input}
            />
          </div>

          <div style={styles.formField}>
            <label style={styles.label}>시장 선택</label>
            <select
              value={market}
              onChange={(e) => setMarket(e.target.value)}
              style={styles.input}
            >
              <option value="">-- 시장을 선택하세요 --</option>
              {markets.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>

          <div style={styles.formField}>
            <label style={styles.label}>상점 위치 (호수/칸)</label>
            <input
              type="text"
              value={stallNo}
              onChange={(e) => setStallNo(e.target.value)}
              placeholder="예) A-12, 2층 201"
              style={styles.input}
            />
          </div>
        </div>
      )}

      <button onClick={onSubmit} style={styles.submitButton}>
        설정 완료
      </button>

      <div style={styles.note}>{note}</div>
    </div>
  );
}