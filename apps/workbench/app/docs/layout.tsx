import {DocsNav} from "@/components/docs";
export default function Layout({children}: {children: React.ReactNode}) { return <div className="docsShell"><DocsNav/><div>{children}</div></div>; }
