import type {Metadata} from 'next';
import './globals.css';
export const metadata:Metadata={title:'PolyQuant • Paper Research Terminal',description:'Local Polymarket US BTC research. Real data, paper execution only.'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en" data-theme="dark"><body>{children}</body></html>;}
