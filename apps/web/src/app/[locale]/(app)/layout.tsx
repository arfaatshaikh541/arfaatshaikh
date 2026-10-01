import { asLocale } from "@/i18n/route-locale";
import { ProtectedShell } from "@/components/protected-shell";export default async function Layout({children,params}:{children:React.ReactNode;params:Promise<{locale:string}>}){const {locale:rawLocale}=await params;const locale=asLocale(rawLocale);return <ProtectedShell locale={locale}>{children}</ProtectedShell>}
