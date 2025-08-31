import NextAuth from "next-auth";
import GoogleProvider from "next-auth/providers/google";

const handler = NextAuth({
  trustHost: true,
  session: { strategy: "jwt" },
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET,
      authorization: { params: { scope: "openid email profile" } },
    }),
  ],
  callbacks: {
    async jwt({ token, account, profile }) {
      if (account?.id_token) token.id_token = account.id_token; // ← 중요
      if (profile?.sub) token.google_sub = profile.sub;
      return token;
    },
    async session({ session, token }) {
      session.id_token = token.id_token || null;               // ← 중요
      session.google_sub = token.google_sub || null;
      return session;
    },
  },
});

export { handler as GET, handler as POST };
