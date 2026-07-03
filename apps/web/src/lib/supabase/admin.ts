import { createClient as createSupabaseClient } from "@supabase/supabase-js";

// service_role: обходит RLS. Только на сервере (провижининг тенанта/пользователя).
export const createAdminClient = () =>
  createSupabaseClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL ?? "",
    process.env.SUPABASE_SERVICE_ROLE_KEY ?? "",
    { auth: { autoRefreshToken: false, persistSession: false } },
  );
