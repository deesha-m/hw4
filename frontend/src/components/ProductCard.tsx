import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { formatPrice } from '../api.ts'

// The fields a card needs. Both full catalogue products and chat page results fit this shape.
export type CardProduct = {
  product_id: string
  name: string
  price: number
  image_url: string
  total_stock: number
  description: string
  garment_type?: string
  sizes_in_stock?: string[]
}

function shorten(text: string, max = 90): string {
  return text.length <= max ? text : `${text.slice(0, max).trimEnd()}…`
}

type Props = {
  product: CardProduct
  // Position in a freshly loaded grid; when set, the card fades in with a small stagger.
  revealIndex?: number
}

// A museum-mount card: photo on the stone mount with an inset frame, a caption plate, and a
// hanging tag when stock is limited.
export default function ProductCard({ product, revealIndex }: Props) {
  const reveal = revealIndex !== undefined
  const sizes = product.sizes_in_stock
  const tag =
    product.total_stock === 0
      ? { text: 'Sold out', tone: 'out' }
      : sizes && sizes.length > 0 && sizes.length <= 2
        ? { text: `Last sizes: ${sizes.join(', ')}`, tone: 'low' }
        : null

  return (
    <Link
      to={`/products/${product.product_id}`}
      className={`card ${reveal ? 'reveal' : ''}`}
      style={reveal ? ({ '--i': Math.min(revealIndex, 12) } as CSSProperties) : undefined}
    >
      <div className="card-image">
        <img src={product.image_url} alt={product.name} loading="lazy" />
        {tag && <span className={`card-tag ${tag.tone}`}>{tag.text}</span>}
      </div>
      <div className="card-body">
        {product.garment_type && <span className="plate">{product.garment_type}</span>}
        <div className="card-title">
          <h3>{product.name}</h3>
          <span className="price">{formatPrice(product.price)}</span>
        </div>
        <p className="muted">{shorten(product.description)}</p>
      </div>
    </Link>
  )
}
