# Project Infrastructure & Credentials Memo

## Server (from developer-status-2026-02-25.md)
- **Host**: `(IP to be provided)` (Germany, Hetzner)
- **Specs**: AMD Ryzen 9 7950X3D, 128 GB DDR5 ECC, 2x1.92 TB NVMe SSD
- **Docker Container**: TreeJar container already created.
- **Action Items**: 
  - Need to expand limits from 2 vCPU / 2GB to 4 vCPU / 8GB. 
  - Need to set up Qdrant (6333), Redis (6379), FastAPI (8000)
  - Nginx proxy: noor.starec.ai -> container
- **Database Recommendation**: Client requested replacing local Postgres with cloud **Supabase**.
  - ⚠️ **CRITICAL - Supabase Pooler Is Disabled or Unreachable**: The connection string `aws-0-ap-south-1.pooler.supabase.com` returns `Tenant or user not found`. This means Connection Pooling is currently NOT enabled in the Supabase Dashboard, or IPv4 pooling is misconfigured. Direct IPv6 connections (`db.vlxgzhbtnwysaqonvlte.supabase.co`) also fail because the environment doesn't support IPv6. 
  - **Action Required**: The user must go to Supabase Dashboard -> Project Settings -> Database -> Connection Pooling, check "Enable connection pooling", ensure Mode is "Transaction", and use the provided pooler connection string.
- **LLM**: Client requested using **OpenRouter** instead of direct DeepSeek, for fallback functionality.

## Credentials
- Wazzup and Zoho API keys were successfully injected from the private `Starec-net/noor-ai-seller` repository and tested.
- **OpenRouter API Key**: Successfully added and verified. OpenRouter API is reachable and correctly responds.
