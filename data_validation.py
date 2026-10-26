"""Validate and independently refresh dashboard tabs."""


def collect_tab(category, collector, previous, attempted_at):
    """Keep a failed tab's original rows and last successful timestamp."""
    old_rows = [row for row in previous if row.get('category') == category]
    old_metadata = next((row for row in previous
                         if row.get('category') == 'collection_status'), {})
    old_status = old_metadata.get('tabs', {}).get(category, {})
    last_success = old_status.get('last_success') or max(
        (row.get('time', '') for row in old_rows), default='')
    try:
        rows = collector()
        validate_snapshot(rows)
        if any(row.get('category') != category for row in rows):
            raise ValueError('수집 결과의 탭이 일치하지 않습니다.')
        if category == 'market_status' and any(
            '수집실패' in item.get('flags', [])
            for row in rows for item in row.get('market_status', [])
        ):
            raise ValueError('시장 상태 일부 조회 실패')
        return rows, {'state': 'ok', 'last_success': attempted_at,
                      'attempted_at': attempted_at, 'error': ''}
    except Exception as error:
        print(f'[{category}] 수집 실패, 기존 {len(old_rows)}개 유지: {type(error).__name__}: {error}')
        return old_rows, {'state': 'stale' if old_rows else 'unavailable',
                          'last_success': last_success, 'attempted_at': attempted_at,
                          'error': f'{type(error).__name__}: {error}'}


def validate_snapshot(results, previous=()):
    if not isinstance(results, list) or not results:
        raise ValueError('수집 결과가 비어 있습니다.')
    categories = {row.get('category') for row in results}
    expected = {row.get('category') for row in previous} - {None, 'market_status', 'yang_stock', 'collection_status'}
    missing = expected - categories
    if missing:
        raise ValueError(f'기존 탭의 수집 결과가 사라졌습니다: {sorted(missing)}')
    for category in ('domestic_theme', 'domestic_value'):
        rows = [row for row in results if row.get('category') == category]
        if rows and all(row.get('change_1m') in (None, '', 'N/A') for row in rows):
            raise ValueError(f'{category}: 모든 종목의 일봉 조회가 실패했습니다.')
