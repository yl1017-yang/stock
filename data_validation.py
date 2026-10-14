"""Reject incomplete collection before replacing the dashboard snapshot."""


def validate_snapshot(results, previous=()):
    if not isinstance(results, list) or not results:
        raise ValueError('수집 결과가 비어 있습니다.')
    categories = {row.get('category') for row in results}
    expected = {row.get('category') for row in previous} - {None, 'market_status'}
    missing = expected - categories
    if missing:
        raise ValueError(f'기존 탭의 수집 결과가 사라졌습니다: {sorted(missing)}')
    for category in ('domestic_theme', 'domestic_value'):
        rows = [row for row in results if row.get('category') == category]
        if rows and all(row.get('change_1m') in (None, '', 'N/A') for row in rows):
            raise ValueError(f'{category}: 모든 종목의 일봉 조회가 실패했습니다.')
