import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchProducts, fetchWeather, openChat, type Product, type WeatherPick } from '../api.ts'
import { isCollegeProduct, useCollege } from '../college.tsx'
import ProductCard from '../components/ProductCard.tsx'
import Storefront, { type ShopWindow } from '../components/Storefront.tsx'

const inFamily = (p: Product, word: string) => p.total_stock > 0 && p.garment_type.toLowerCase().includes(word)

const highlights = [
  {
    title: 'Officially licensed',
    text: 'Every piece carries real Yale marks, so the Bulldog on your chest is the genuine article.',
  },
  {
    title: 'Made for every Eli',
    text: 'Students, alumni, parents and lifelong fans all find something that fits their kind of Yale pride.',
  },
  {
    title: 'Right on Broadway',
    text: 'Shop online or stop by our New Haven store, a short walk from Old Campus.',
  },
]

export default function Home() {
  const [products, setProducts] = useState<Product[]>([])
  const [weather, setWeather] = useState<WeatherPick | null>(null)
  const { college } = useCollege()

  useEffect(() => {
    fetchProducts().then(setProducts).catch(() => setProducts([]))
    fetchWeather().then(setWeather)
  }, [])

  const collegePieces = useMemo(
    () => products.filter((p) => isCollegeProduct(p.name, college)),
    [products, college],
  )

  // The right-hand window becomes the shopper's college display in college mode.
  const windows = useMemo((): { left: ShopWindow; right: ShopWindow } => {
    const hoodies = products.filter((p) => inFamily(p, 'hood'))
    const crews = products.filter((p) => inFamily(p, 'crew') && !p.garment_type.includes('quarter'))
    return {
      left: { label: 'Hoodies', category: 'hoodie', products: hoodies.slice(0, 2) },
      right:
        college && collegePieces.length > 0
          ? { label: college, category: `college:${college}`, products: collegePieces.slice(0, 2) }
          : { label: 'Crewnecks', category: 'crewneck', products: crews.slice(1, 3) },
    }
  }, [products, college, collegePieces])

  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Now open · 57 Broadway, New Haven</p>
          <h1>
            Step inside <span className="accent">57 Broadway.</span>
          </h1>
          <p className="lead">
            Hoodies for late nights in the library, crewnecks for crisp walks across Old Campus, and
            tees for The Game. Peek in the windows, or step through the door and ask the shop.
          </p>
          <div className="hero-actions">
            <Link to="/products" className="button">
              Shop the collection
            </Link>
            <button type="button" className="button ghost" onClick={() => openChat()}>
              Ask the shop
            </button>
          </div>
        </div>
        <Storefront left={windows.left} right={windows.right} />
      </section>

      {weather && weather.products.length > 0 && (
        <section className="section weather-strip">
          <div className="section-head">
            <div>
              <p className="eyebrow">
                Today on Broadway · {weather.temperature_f}°F, {weather.condition}
              </p>
              <h2>{weather.headline}</h2>
            </div>
            <Link to={`/products?category=${weather.category}`} className="text-link">
              See all →
            </Link>
          </div>
          <div className="grid">
            {weather.products.map((p) => (
              <ProductCard key={p.product_id} product={{ ...p, description: p.short_description }} />
            ))}
          </div>
        </section>
      )}

      {college && (
        <section className="section college-row">
          <div className="section-head">
            <div>
              <p className="eyebrow">College mode</p>
              <h2>For {college}</h2>
            </div>
            {collegePieces.length > 0 && (
              <Link to={`/products?category=${encodeURIComponent(`college:${college}`)}`} className="text-link">
                See all →
              </Link>
            )}
          </div>
          {collegePieces.length > 0 ? (
            <div className="grid">
              {collegePieces.slice(0, 4).map((p) => (
                <ProductCard key={p.product_id} product={p} />
              ))}
            </div>
          ) : (
            <p className="muted">
              We don't carry {college}-specific pieces yet, so here's to the classics.{' '}
              <Link to="/products?category=crewneck" className="text-link">
                Shop Yale crewnecks →
              </Link>
            </p>
          )}
        </section>
      )}

      <section className="section highlights">
        {highlights.map((item) => (
          <div key={item.title} className="highlight">
            <h3>{item.title}</h3>
            <p className="muted">{item.text}</p>
          </div>
        ))}
      </section>
    </>
  )
}
