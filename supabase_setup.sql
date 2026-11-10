-- KAMERA KATALOGIM: PIN-kodli server versiyasi
-- Supabase Dashboard -> SQL Editor -> New query -> shu faylni to'liq joylang -> Run.
-- Bu sxema faqat Render serveri orqali ishlaydi. Brauzer Supabase kalitini olmaydi.

create table if not exists public.cameras (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  brand text not null default '',
  category text not null default 'Boshqa',
  price numeric(14,2) not null default 0 check (price >= 0),
  currency text not null default 'UZS' check (currency in ('UZS','USD')),
  notes text not null default '',
  image_path text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Oldingi ko'rsatmadagi owner_id ga bog'liq siyosatni avval olib tashlaymiz.
drop policy if exists "Owner can manage own cameras" on public.cameras;
-- owner_id ustuni bo'lsa, uni olib tashlaymiz; kamera yozuvlari saqlanib qoladi.
alter table public.cameras drop column if exists owner_id;

alter table public.cameras enable row level security;
revoke all on table public.cameras from anon, authenticated;
grant all on table public.cameras to service_role;

-- Rasmlar private bucketda saqlanadi. Faqat serverdagi service-role key ularga kira oladi.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('camera-photos', 'camera-photos', false, 10485760, array['image/jpeg'])
on conflict (id) do update set
  public = false,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

-- Avvalgi versiyadagi owner_id ga bog'liq storage siyosatlarini olib tashlaymiz.
drop policy if exists "Owner can read own camera photos" on storage.objects;
drop policy if exists "Owner can upload own camera photos" on storage.objects;
drop policy if exists "Owner can update own camera photos" on storage.objects;
drop policy if exists "Owner can delete own camera photos" on storage.objects;

-- Realtime shart emas: sayt ma'lumotni 15 soniyada bir yangilab turadi.
