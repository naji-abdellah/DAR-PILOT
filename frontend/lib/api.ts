export interface Listing {
  id: number;
  title: string;
  description: string;
  price_mad: number;
  city: string;
  neighborhood: string;
  property_type: string;
  status: string;
  agent_id: number | null;
  created_at: string;
}

export interface Lead {
  id: number;
  name: string;
  phone: string | null;
  email: string;
  message: string;
  listing_id: number | null;
  status: string;
  created_at: string;
}

export interface Visit {
  id: number;
  lead_id: number;
  listing_id: number;
  scheduled_at: string;
  status: string;
  notes: string;
  created_at: string;
}

export interface User {
  id: number;
  username: string;
  email: string;
  role: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...opts?.headers },
    ...opts,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(detail || `Request failed with status ${res.status}`);
  }
  return (await res.json()) as T;
}

export const api = {
  getListings: () => request<Listing[]>("/listings"),
  getListing: (id: number) => request<Listing>(`/listings/${id}`),
  createLead: (body: {
    name: string;
    phone?: string | null;
    email: string;
    message?: string;
    listing_id?: number | null;
    status?: string;
  }) => request<Lead>("/leads", {
    method: "POST",
    body: JSON.stringify(body),
  }),
  createListing: (body: {
    title: string;
    description?: string;
    price_mad: number;
    city: string;
    neighborhood?: string;
    property_type: string;
    status?: string;
    agent_id?: number | null;
  }, token: string) => request<Listing>("/listings", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  }),
  getLead: (id: number, token: string) => request<Lead>(`/leads/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
  }),
  getLeadsForListing: (listingId: number, token: string) => request<Lead[]>(`/leads/listing/${listingId}`, {
    headers: { Authorization: `Bearer ${token}` },
  }),
  login: (username: string, password: string) =>
    request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  register: (body: {
    username: string;
    email: string;
    password: string;
    role?: string;
  }) => request<User>("/auth/register", {
    method: "POST",
    body: JSON.stringify(body),
  }),
};

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("darpilot_token");
}

export function setToken(token: string) {
  if (typeof window === "undefined") return;
  localStorage.setItem("darpilot_token", token);
}

export function clearToken() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("darpilot_token");
}


