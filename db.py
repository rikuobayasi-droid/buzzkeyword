"""
db.py — Supabase接続クライアント
"""
import os
from supabase import create_client, Client

_client: Client = None

def get_client() -> Client:
    global _client
    if _client is None:
        import streamlit as st
        url = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL", ""))
        key = st.secrets.get("SUPABASE_KEY", os.environ.get("SUPABASE_KEY", ""))
        if not url or not key:
            raise ValueError("SUPABASE_URL と SUPABASE_KEY を設定してください")
        _client = create_client(url, key)
    return _client

def sb_select(table, filters=None, order=None, limit=None):
    import streamlit as st
    try:
        q = get_client().table(table).select("*")
        if filters:
            for col, val in filters.items(): q = q.eq(col, val)
        if order:
            desc = order.startswith("-")
            q = q.order(order.lstrip("-"), desc=desc)
        if limit: q = q.limit(limit)
        return q.execute().data or []
    except Exception as e:
        st.error(f"DB取得エラー({table}): {e}"); return []

def sb_insert(table, data):
    import streamlit as st
    try:
        res = get_client().table(table).insert(data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        st.error(f"DB挿入エラー({table}): {e}"); return None

def sb_upsert(table, data, on_conflict=None):
    import streamlit as st
    try:
        q = get_client().table(table).upsert(data)
        if on_conflict: q = q.on_conflict(on_conflict)
        res = q.execute()
        return res.data[0] if res.data else None
    except Exception as e:
        st.error(f"DB upsertエラー({table}): {e}"); return None

def sb_update(table, data, filters):
    import streamlit as st
    try:
        q = get_client().table(table).update(data)
        for col, val in filters.items(): q = q.eq(col, val)
        q.execute(); return True
    except Exception as e:
        st.error(f"DB更新エラー({table}): {e}"); return False

def sb_delete(table, filters):
    import streamlit as st
    try:
        q = get_client().table(table).delete()
        for col, val in filters.items(): q = q.eq(col, val)
        q.execute(); return True
    except Exception as e:
        st.error(f"DB削除エラー({table}): {e}"); return False
