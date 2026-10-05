import { useNavigate } from 'react-router-dom'
import { openChat, type Product } from '../api.ts'

export type ShopWindow = {
  label: string
  category: string // Products page ?category= value
  products: Product[]
}

type Props = { left: ShopWindow; right: ShopWindow }

// "Walk into the store": 57 Broadway drawn in CSS. Each display window shows real products
// and opens that category; the door opens the shop-counter chat.
export default function Storefront({ left, right }: Props) {
  const navigate = useNavigate()

  const renderWindow = (w: ShopWindow, side: 'left' | 'right') => (
    <button
      type="button"
      className={`shop-window ${side}`}
      onClick={() => navigate(`/products?category=${encodeURIComponent(w.category)}`)}
      aria-label={`Shop ${w.label}`}
    >
      <span className="glass">
        <span className="display">
          {w.products.slice(0, 2).map((p, i) => (
            <img key={p.product_id} src={p.image_url} alt="" className={`mannequin m${i}`} />
          ))}
        </span>
        <span className="shelf" />
        <span className="reflection" />
      </span>
      <span className="window-plate">
        <em>Shop</em> {w.label} <span aria-hidden="true">→</span>
      </span>
    </button>
  )

  return (
    <div className="storefront" aria-label="The Campus Customs storefront at 57 Broadway">
      <div className="facade">
        <div className="upper-floor" aria-hidden="true">
          <span className="upper-window" />
          <span className="upper-window lit" />
          <span className="upper-window" />
        </div>
        <div className="signboard">
          <span className="sign-name">Campus Customs</span>
          <span className="sign-sub">Officially licensed Yale apparel</span>
        </div>
        <div className="awning" aria-hidden="true" />
        <div className="shopfront">
          {renderWindow(left, 'left')}
          <button
            type="button"
            className="door"
            onClick={() => openChat()}
            aria-label="Step inside: open the shop chat"
          >
            <span className="door-frame">
              <span className="door-inside" aria-hidden="true">
                <span>Come on in</span>
              </span>
              <span className="door-leaf">
                <span className="door-glass" />
                <span className="open-sign">Open</span>
                <span className="handle" />
                <span className="door-number">57</span>
              </span>
            </span>
            <span className="door-hint">Step inside</span>
          </button>
          {renderWindow(right, 'right')}
        </div>
        <div className="stoop" aria-hidden="true" />
      </div>
      <div className="sidewalk" aria-hidden="true">
        <span>Broadway</span>
      </div>
    </div>
  )
}
