// Talks to the FastAPI backend in backend/main.py (proxied by Vite).

export type StockLevel = {
  size: string
  quantity: number
}

export type Product = {
  product_id: string
  name: string
  garment_type: string
  description: string
  colors: string[]
  search_tags: string[]
  image_url: string
  price: number
  total_stock: number
  sizes_in_stock: string[]
  inventory?: StockLevel[]
}

export type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
}

export type User = {
  id: number
  first_name: string
  last_name: string
  email: string
}

export type RegisterInput = {
  first_name: string
  last_name: string
  email: string
  password: string
  confirm_password: string
}

// Turns FastAPI errors (a string, or a list of validation errors) into one readable message.
async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail) && body.detail.length > 0) {
      return String(body.detail[0].msg).replace(/^Value error, /, '')
    }
  } catch {
    // fall through to a generic message
  }
  return `Something went wrong (${response.status})`
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify(body),
  })
  if (!response.ok) throw new Error(await errorMessage(response))
  return (response.status === 204 ? undefined : await response.json()) as T
}

export function register(input: RegisterInput): Promise<User> {
  return postJson<User>('/api/auth/register', input)
}

export function logIn(email: string, password: string): Promise<User> {
  return postJson<User>('/api/auth/login', { email, password })
}

export function logOut(): Promise<void> {
  return postJson<void>('/api/auth/logout', {})
}

export async function fetchCurrentUser(): Promise<User | null> {
  const response = await fetch('/api/auth/me', { credentials: 'same-origin' })
  return response.ok ? ((await response.json()) as User) : null
}

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(response.status === 404 ? 'Not found' : `Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}

export function fetchProducts(): Promise<Product[]> {
  return getJson<Product[]>('/api/products')
}

export function fetchProduct(productId: string): Promise<Product> {
  return getJson<Product>(`/api/products/${encodeURIComponent(productId)}`)
}

export function formatPrice(price: number): string {
  return `$${price.toFixed(0)}`
}

export type ChatProduct = {
  product_id: string
  name: string
  price: number
  image_url: string
  total_stock: number
}

export type PageProduct = {
  product_id: string
  name: string
  garment_type: string
  price: number
  image_url: string
  short_description: string
  total_stock: number
  sizes_in_stock: string[]
}

// Chat search results for the Products page (set when the agent calls show_products_on_page).
export type PageResults = {
  title: string
  query: string
  total_matches: number
  products: PageProduct[]
}

// The /api/chat contract: reply text, optional in-chat cards, optional page results.
export type ChatReply = {
  reply: string
  products: ChatProduct[]
  page: PageResults | null
}

// Where the shopper is, so "do you have this in pink?" on a product page means that product.
// The backend looks up names and prices itself; only the path and IDs come from here.
export type PageContext = {
  path: string
  product_id: string | null
  results_title: string | null
  visible_product_ids: string[]
  college: string | null
}

export type SavedChatMessage = {
  role: 'user' | 'assistant'
  content: string
  products: ChatProduct[]
  created_at: string
}

// Sends the new message to the PydanticAI agent behind FastAPI. The session cookie goes along
// automatically: for logged-in shoppers the backend uses (and saves) their stored history, so
// `history` only matters for guests.
export function sendChatMessage(message: string, history: ChatMessage[], page: PageContext): Promise<ChatReply> {
  return postJson<ChatReply>('/api/chat', { message, history: history.slice(-12), page })
}

export async function fetchChatHistory(): Promise<SavedChatMessage[]> {
  const response = await fetch('/api/chat/history', { credentials: 'same-origin' })
  return response.ok ? ((await response.json()) as SavedChatMessage[]) : []
}

export function clearChatHistory(): Promise<void> {
  return postJson<void>('/api/chat/history/clear', {})
}

// Live New Haven weather and 4 in-stock products that suit it (GET /api/weather).
export type WeatherPick = {
  temperature_f: number
  feels_like_f: number
  condition: string
  category: string
  headline: string
  products: PageProduct[]
}

export async function fetchWeather(): Promise<WeatherPick | null> {
  try {
    const response = await fetch('/api/weather')
    return response.ok ? ((await response.json()) as WeatherPick) : null
  } catch {
    return null
  }
}

// Ask the chat widget to open (the storefront door does this). Optionally send a message.
export function openChat(message?: string) {
  window.dispatchEvent(new CustomEvent('cc:open-chat', { detail: { message } }))
}
