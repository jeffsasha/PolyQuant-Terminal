import type {Metadata,Viewport} from 'next';
import Backdrop from '../components/Backdrop';
import './globals.css';
export const metadata:Metadata={title:'PolyQuant • Paper Research Terminal',description:'Local Polymarket US BTC research. Real data, paper execution only.'};
export const viewport:Viewport={themeColor:'#010102',colorScheme:'dark light'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en" data-theme="dark"><body><Backdrop/>{children}</body></html>;}
