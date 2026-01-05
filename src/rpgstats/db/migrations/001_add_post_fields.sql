alter table raw_posts
  add column if not exists author text,
  add column if not exists tags text[],
  add column if not exists group_name text,
  add column if not exists download_url text,
  add column if not exists file_size_bytes bigint,
  add column if not exists youtube_urls text[];

