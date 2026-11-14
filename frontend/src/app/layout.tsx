import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TerraPulse — Earth System Trend Detective",
  description:
    "Find trends in NASA Earth-system data (MERRA-2 and MODIS) and test whether they are statistically significant, robust to the dates chosen, and supported by a second dataset.",
  authors: [{ name: "Team Orbital Alpha" }],
  // Required acknowledgement of SI-generated code, in metadata as well as in visible text.
  other: {
    "si-disclosure":
      "Code, tests and documentation were generated with an SI coding assistant (Anthropic Claude) during the NASA Space Apps Challenge, November 14-15, 2026. See the repository README.",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full">{children}</body>
    </html>
  );
}
