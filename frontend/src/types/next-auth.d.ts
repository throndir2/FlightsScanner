// Module augmentation: carry the backend user id + access token through the
// NextAuth session and JWT. See src/lib/auth.ts and docs/auth-and-security.md.
import type { DefaultSession } from "next-auth";

declare module "next-auth" {
  interface Session {
    userId?: string;
    accessToken?: string;
    user?: DefaultSession["user"] & { id?: string };
  }

  interface User {
    accessToken?: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    userId?: string;
    accessToken?: string;
  }
}
