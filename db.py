"""
db.py — Supabase接続クライアント（upsertバグ修正版）
"""
import os

_client = None

def get_client():
    global _client
    if _client is None:
        import streamlit as st
        from supabase import create_client
        url = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL", ""))
        key = st.secrets.get("SUPABASE_KEY", os.environ.get("SUPABASE_KEY", ""))
        if not url or not key:
            raise ValueError("SUPABASE_URL と SUPABASE_KEY を設定してください")
        _client = create_client(url, key)
    return _client

def sb_select(table, filters=None, order=None, limit=None):
    """
    Supabaseのデフォルト上限は1000件。
    limit未指定の場合は全件取得する（ページネーション）。
    """
    import streamlit as st
    try:
        client = get_client()

        # limit指定あり → そのまま取得
        if limit:
            q = client.table(table).select("*")
            if filters:
                for col, val in filters.items():
                    q = q.eq(col, val)
            if order:
                desc = order.startswith("-")
                q = q.order(order.lstrip("-"), desc=desc)
            q = q.limit(limit)
            return q.execute().data or []

        # limit未指定 → 1000件ずつページネーションで全件取得
        all_data = []
        page_size = 1000
        offset = 0
        while True:
            q = client.table(table).select("*")
            if filters:
                for col, val in filters.items():
                    q = q.eq(col, val)
            if order:
                desc = order.startswith("-")
                q = q.order(order.lstrip("-"), desc=desc)
            q = q.range(offset, offset + page_size - 1)
            rows = q.execute().data or []
            all_data.extend(rows)
            if len(rows) < page_size:
                break  # 最後のページ
            offset += page_size
        return all_data

    except Exception as e:
        st.error(f"DB取得エラー({table}): {e}")
        return []

def sb_insert(table, data):
    import streamlit as st
    try:
        res = get_client().table(table).insert(data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        st.error(f"DB挿入エラー({table}): {e}")
        return None

def sb_upsert(table, data):
    """
    UPSERTはSupabaseのupsert()のみ使用。
    on_conflict はSupabaseがPKを自動検出するため不要。
    テーブルのUNIQUE制約はSupabase側で設定すること。
    """
    import streamlit as st
    try:
        res = get_client().table(table).upsert(data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        st.error(f"DB upsertエラー({table}): {e}")
        return None

def sb_update(table, data, filters):
    import streamlit as st
    try:
        q = get_client().table(table).update(data)
        for col, val in filters.items():
            q = q.eq(col, val)
        q.execute()
        return True
    except Exception as e:
        st.error(f"DB更新エラー({table}): {e}")
        return False

def sb_delete(table, filters):
    import streamlit as st
    try:
        q = get_client().table(table).delete()
        for col, val in filters.items():
            q = q.eq(col, val)
        q.execute()
        return True
    except Exception as e:
        st.error(f"DB削除エラー({table}): {e}")
        return False
