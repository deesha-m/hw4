import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchProducts, type Product } from '../api.ts'
import { useChatResults } from '../chatResults.tsx'
import { isCollegeProduct, useCollege } from '../college.tsx'
import ProductCard, { type CardProduct } from '../components/ProductCard.tsx'

// The catalogue uses 22 garment-type labels; these group them the way shoppers think.
// Mirrors garment_family() in backend/tools.py.
const CATEGORIES = [
  { key: 'all', label: 'All' },
  { key: 'hoodie', label: 'Hoodies' },
  { key: 'crewneck', label: 'Crewnecks' },
  { key: 't-shirt', label: 'T-shirts' },
  { key: 'quarter-zip', label: 'Quarter-zips' },
  { key: 'jacket', label: 'Jackets & fleece' },
] as const

type CategoryKey = (typeof CATEGORIES)[number]['key'] | 'other' | 'college'
type SortKey = 'featured' | 'price-asc' | 'price-desc' | 'name'
const SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL']

function categoryOf(garmentType: string): CategoryKey {
  const g = garmentType.toLowerCase()
  if (g.includes('hood')) return 'hoodie'
  if (g.includes('quarter')) return 'quarter-zip'
  if (g.includes('jacket') || g.includes('fleece')) return 'jacket'
  if (g.includes('t-shirt') || g.includes('tee')) return 't-shirt'
  if (g.includes('crew') || g.includes('sweatshirt')) return 'crewneck'
  return 'other'
}

type Listed = CardProduct & { category: CategoryKey | null; college: boolean }

export default function Products() {
  const [products, setProducts] = useState<Product[]>([])
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [query, setQuery] = useState('')
  const { college } = useCollege()
  // The category lives in the URL (?category=hoodie, or college:Davenport), so storefront
  // windows and weather links can open the page pre-filtered.
  const [params, setParams] = useSearchParams()
  const rawCategory = params.get('category') ?? 'all'
  const category: CategoryKey = rawCategory.startsWith('college:')
    ? 'college'
    : ([...CATEGORIES.map((c) => c.key), 'other'] as string[]).includes(rawCategory)
      ? (rawCategory as CategoryKey)
      : 'all'
  const collegeFilter = category === 'college' ? rawCategory.slice('college:'.length) : college
  const setCategory = (key: CategoryKey) => {
    const next = new URLSearchParams(params)
    if (key === 'all') next.delete('category')
    else next.set('category', key === 'college' && college ? `college:${college}` : key)
    setParams(next, { replace: true })
  }
  const [sort, setSort] = useState<SortKey>('featured')
  const [size, setSize] = useState('')  // '' = any size
  const { results, version, clear } = useChatResults()

  useEffect(() => {
    fetchProducts()
      .then((data) => {
        setProducts(data)
        setStatus('ready')
      })
      .catch(() => setStatus('error'))
  }, [])

  // New chat results: jump to the top so the shopper sees them land.
  useEffect(() => {
    if (results) window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [results, version])

  const garmentTypes = useMemo(
    () => new Map(products.map((p) => [p.product_id, p.garment_type])),
    [products],
  )

  // Chat results replace the full catalogue until the shopper clears them.
  const source: Listed[] = useMemo(() => {
    const base: CardProduct[] = results
      ? results.products.map((p) => ({ ...p, description: p.short_description }))
      : products
    return base.map((p) => {
      const type = p.garment_type || garmentTypes.get(p.product_id)
      return { ...p, category: type ? categoryOf(type) : null, college: isCollegeProduct(p.name, collegeFilter) }
    })
  }, [results, products, garmentTypes, collegeFilter])

  // Search and stock filters apply first, so category counts reflect them.
  const searched = useMemo(() => {
    const q = query.trim().toLowerCase()
    return source.filter(
      (p) =>
        (!q || `${p.name} ${p.description}`.toLowerCase().includes(q)) &&
        (size ? (p.sizes_in_stock ?? []).includes(size) : true),
    )
  }, [source, query, size])

  const counts = useMemo(() => {
    const tally: Record<string, number> = { all: searched.length }
    for (const p of searched) {
      if (p.category) tally[p.category] = (tally[p.category] ?? 0) + 1
      if (p.college) tally.college = (tally.college ?? 0) + 1
    }
    return tally
  }, [searched])

  const visible = useMemo(() => {
    const list =
      category === 'all'
        ? searched
        : category === 'college'
          ? searched.filter((p) => p.college)
          : searched.filter((p) => p.category === category)
    const sorted = [...list]
    if (sort === 'price-asc') sorted.sort((a, b) => a.price - b.price || a.name.localeCompare(b.name))
    if (sort === 'price-desc') sorted.sort((a, b) => b.price - a.price || a.name.localeCompare(b.name))
    if (sort === 'name') sorted.sort((a, b) => a.name.localeCompare(b.name))
    return sorted
  }, [searched, category, sort])

  const filtersActive = query !== '' || category !== 'all' || sort !== 'featured' || size !== ''
  function clearFilters() {
    setQuery('')
    setCategory('all')
    setSort('featured')
    setSize('')
  }

  const total = results ? results.total_matches : products.length
  const countLabel = results
    ? `${results.total_matches} ${results.total_matches === 1 ? 'match' : 'matches'}` +
      (visible.length !== results.total_matches ? `, showing ${visible.length}` : '')
    : status === 'ready'
      ? `${visible.length} of ${total} items`
      : 'Yale apparel for every season'

  return (
    <section className="section">
      {results && (
        <div className="chat-banner" key={version}>
          <span className="eyebrow">From your chat</span>
          <button type="button" className="text-link" onClick={clear}>
            Show all products
          </button>
        </div>
      )}
      <div className="section-head">
        <div>
          <h1 key={results ? `r${version}` : 'all'} className={results ? 'reveal-title' : ''}>
            {results ? results.title : 'Products'}
          </h1>
          <p className="muted">{countLabel}</p>
        </div>
        <input
          className="search"
          type="search"
          placeholder={results ? 'Filter these results…' : 'Search hoodies, navy, rivalry…'}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          aria-label="Search products"
        />
      </div>

      <div className="toolbar">
        <div className="category-chips" role="group" aria-label="Filter by category">
          {collegeFilter && (counts.college ?? 0) > 0 && (
            <button
              type="button"
              className={`category-chip college ${category === 'college' ? 'active' : ''}`}
              aria-pressed={category === 'college'}
              onClick={() => setCategory('college')}
            >
              {collegeFilter} <span>{counts.college}</span>
            </button>
          )}
          {CATEGORIES.map((c) => {
            const count = counts[c.key] ?? 0
            if (c.key !== 'all' && count === 0 && category !== c.key) return null
            return (
              <button
                key={c.key}
                type="button"
                className={`category-chip ${category === c.key ? 'active' : ''}`}
                aria-pressed={category === c.key}
                onClick={() => setCategory(c.key)}
              >
                {c.label} <span>{count}</span>
              </button>
            )
          })}
        </div>
        <div className="toolbar-right">
          <label className="sort">
            In stock in
            <select value={size} onChange={(e) => setSize(e.target.value)} aria-label="Only show products in stock in this size">
              <option value="">Any size</option>
              {SIZES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label className="sort">
            Sort
            <select value={sort} onChange={(e) => setSort(e.target.value as SortKey)} aria-label="Sort products">
              <option value="featured">Featured</option>
              <option value="price-asc">Price: low to high</option>
              <option value="price-desc">Price: high to low</option>
              <option value="name">Name</option>
            </select>
          </label>
          {filtersActive && (
            <button type="button" className="text-link reset" onClick={clearFilters}>
              Clear filters
            </button>
          )}
        </div>
      </div>

      {!results && status === 'loading' && <p className="muted">Loading products…</p>}
      {!results && status === 'error' && (
        <p className="error">Couldn't load products. Is the backend running on port 8000?</p>
      )}
      {(results || status === 'ready') && visible.length === 0 && (
        <p className="muted">
          No products match these filters.{' '}
          {filtersActive && (
            <button type="button" className="text-link reset" onClick={clearFilters}>
              Clear filters
            </button>
          )}
        </p>
      )}

      <div className="grid" key={results ? `grid${version}` : 'all'}>
        {visible.map((product, index) => (
          <ProductCard
            key={product.product_id}
            product={product}
            revealIndex={results ? index : undefined}
          />
        ))}
      </div>
    </section>
  )
}
