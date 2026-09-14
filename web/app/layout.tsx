import type { Metadata } from "next";
import "./styles.css";
import "./admin.css";
import "./bank.css";

export const metadata: Metadata = {
  title: "Flowline | Payment success monitor",
  description: "Secure payment operations and routing intelligence.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
