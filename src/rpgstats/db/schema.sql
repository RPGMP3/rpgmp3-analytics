-- Raw ingest table: store “what we saw” so parsing can evolve without re-crawling everything.
create table if not exists raw_posts (
  url text primary key,
  lastmod timestamptz null,

  wp_id bigint null,
  slug text null,

  title text null,
  published_at timestamptz null,
  modified_at timestamptz null,

  content_type text not null default 'unknown', -- session/interview/music/audio_drama/other/unknown

  audio_url text null,
  duration_seconds integer null,
  duration_source text null, -- rss/wp_html/file_probe/manual

  wp_json jsonb null,  -- store raw WP payload for debugging
  fetched_at timestamptz not null default now()
);

create index if not exists idx_raw_posts_content_type on raw_posts(content_type);
create index if not exists idx_raw_posts_wp_id on raw_posts(wp_id);
create index if not exists idx_raw_posts_published_at on raw_posts(published_at);

