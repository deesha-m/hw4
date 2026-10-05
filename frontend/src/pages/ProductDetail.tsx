import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchProduct, formatPrice, openChat, type Product } from '../api.ts'

const LOW_STOCK = 5

export default function ProductDetail() {
  const { productId = '' } = useParams()
  // Results are tagged with the ID they belong to, so a stale product never shows.
  const [result, setResult] = useState<{ id: string; product?: Product; error?: string }>()

  useEffect(() => {
    fetchProduct(productId)
      .then((product) => setResult({ id: productId, product }))
      .catch((err: Error) =>
        setResult({
          id: productId,
          error: err.message === 'Not found' ? 'We couldn\'t find that product.' : 'Couldn\'t load this product.',
        }),
      )
  }, [productId])

  const current = result?.id === productId ? result : undefined
  const product = current?.product
  const error = current?.error

  if (error) {
    return (
      <section className="section">
        <p className="error">{error}</p>
        <Link to="/products" className="text-link">← Back to products</Link>
      </section>
    )
  }
  if (!product) return <section className="section muted">Loading…</section>

  return (
    <section className="section">
      <Link to="/products" className="text-link">← Back to products</Link>
      <div className="detail">
        <div className="detail-image mount">
          <img src={product.image_url} alt={product.name} />
        </div>
        <div className="detail-info">
          <span className="plate">{product.garment_type}</span>
          <h1>{product.name}</h1>
          <p className="detail-price">{formatPrice(product.price)}</p>
          <p className="lead">{product.description}</p>

          <h3>Colors</h3>
          <div className="chips">
            {product.colors.map((color) => (
              <span key={color} className="chip">{color}</span>
            ))}
          </div>

          <h3>Sizes &amp; stock</h3>
          {/* Hanging shop tags, one per size, on a brass rail. */}
          <div className="tag-rail">
            {product.inventory?.map(({ size, quantity }) => {
              const tone = quantity === 0 ? 'out' : quantity <= LOW_STOCK ? 'low' : 'in'
              return (
                <div
                  key={size}
                  className={`size-tag ${tone}`}
                  aria-label={`${size}: ${tone === 'out' ? 'sold out' : `${quantity} in stock`}`}
                >
                  <span className="tag-hole" aria-hidden="true" />
                  <strong>{size}</strong>
                  <span className="tag-note">
                    {tone === 'out' ? 'sold out' : tone === 'low' ? `last ${quantity}!` : 'in stock'}
                  </span>
                  {tone === 'out' && (
                    <svg className="tag-strike" viewBox="0 0 60 60" aria-hidden="true">
                      <path d="M8 50 C 20 36, 36 24, 52 10" />
                    </svg>
                  )}
                </div>
              )
            })}
          </div>
          <p className="muted stock-summary">
            {product.total_stock} units across all sizes.{' '}
            <button type="button" className="text-link inline" onClick={() => openChat('Which sizes of this are in stock?')}>
              Ask the shop about sizes →
            </button>
          </p>
        </div>
      </div>
    </section>
  )
}
