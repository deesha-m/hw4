import { Route, Routes } from 'react-router-dom'
import NavBar from './components/NavBar.tsx'
import ChatWidget from './components/ChatWidget.tsx'
import Home from './pages/Home.tsx'
import Products from './pages/Products.tsx'
import ProductDetail from './pages/ProductDetail.tsx'
import About from './pages/About.tsx'
import LogIn from './pages/LogIn.tsx'
import CreateAccount from './pages/CreateAccount.tsx'
import NotFound from './pages/NotFound.tsx'

export default function App() {
  return (
    <>
      <NavBar />
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/products" element={<Products />} />
          <Route path="/products/:productId" element={<ProductDetail />} />
          <Route path="/about" element={<About />} />
          <Route path="/login" element={<LogIn />} />
          <Route path="/create-account" element={<CreateAccount />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <footer className="footer">
        <span className="footer-seal" aria-hidden="true">CC</span>
        <p className="footer-name">Campus Customs</p>
        <p>57 Broadway · New Haven, Connecticut 06511</p>
        <p className="muted">Officially licensed Yale apparel · Class project demo</p>
      </footer>
      <ChatWidget />
    </>
  )
}
