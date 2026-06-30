import createMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";

export default createMiddleware(routing);

export const config = {
  // все пути кроме api, _next, статики
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};
