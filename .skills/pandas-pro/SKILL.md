---
name: pandas-pro
description: Performs pandas DataFrame operations for data analysis, manipulation, and transformation. Use when working with pandas DataFrames, data cleaning, aggregation, merging, or time series analysis.
license: MIT
metadata:
  author: https://github.com/Jeffallan
  version: "1.1.0"
  domain: data-ml
  triggers: pandas, DataFrame, data manipulation, data cleaning, aggregation, groupby, merge, join, time series, pivot table, data transformation
  role: expert
  scope: implementation
  output-format: code
  related-skills: python-pro
---

# Pandas Pro

Expert pandas developer specializing in efficient data manipulation, analysis, and transformation workflows.

## Core Workflow

1. **Assess data structure** — Examine dtypes, memory usage, missing values, data quality:
   ```python
   print(df.dtypes)
   print(df.memory_usage(deep=True).sum() / 1e6, "MB")
   print(df.isna().sum())
   print(df.describe(include="all"))
   ```
2. **Design transformation** — Plan vectorized operations, avoid loops, identify indexing strategy
3. **Implement efficiently** — Use vectorized methods, method chaining, proper indexing
4. **Validate results** — Check dtypes, shapes, null counts, and row counts:
   ```python
   assert result.shape[0] == expected_rows, f"Row count mismatch: {result.shape[0]}"
   assert result.isna().sum().sum() == 0, "Unexpected nulls after transform"
   ```
5. **Optimize** — Profile memory, apply categorical types, use chunking if needed

## Code Patterns

### Vectorized Operations (before/after)
```python
# BAD: row-by-row iteration
for i, row in df.iterrows():
    df.at[i, 'tax'] = row['price'] * 0.2

# GOOD: vectorized assignment
df['tax'] = df['price'] * 0.2
```

### Safe Subsetting with `.copy()`
```python
# BAD: chained indexing triggers SettingWithCopyWarning
df['A']['B'] = 1

# GOOD: .loc[] with explicit copy when mutating a subset
subset = df.loc[df['status'] == 'active', :].copy()
subset['score'] = subset['score'].fillna(0)
```

### GroupBy Aggregation
```python
summary = (
    df.groupby(['region', 'category'], observed=True)
    .agg(
        total_sales=('revenue', 'sum'),
        avg_price=('price', 'mean'),
        order_count=('order_id', 'nunique'),
    )
    .reset_index()
)
```

### Merge with Validation
```python
merged = pd.merge(
    left_df, right_df,
    on=['customer_id', 'date'],
    how='left',
    validate='m:1',
    indicator=True,
)
unmatched = merged[merged['_merge'] != 'both']
print(f"Unmatched rows: {len(unmatched)}")
merged.drop(columns=['_merge'], inplace=True)
```

### Missing Value Handling
```python
df['price'] = df['price'].ffill().interpolate(method='linear')

for col in df.select_dtypes(include='object'):
    df[col] = df[col].fillna(df[col].mode()[0])
for col in df.select_dtypes(include='number'):
    df[col] = df[col].fillna(df[col].median())
```

### Memory Optimization
```python
df['category'] = df['category'].astype('category')
df['count'] = pd.to_numeric(df['count'], downcast='integer')
df['score'] = pd.to_numeric(df['score'], downcast='float')
print(df.memory_usage(deep=True).sum() / 1e6, "MB after optimization")
```

## Constraints

### MUST DO
- Use vectorized operations instead of loops
- Set appropriate dtypes (categorical for low-cardinality strings)
- Check memory usage with `.memory_usage(deep=True)`
- Handle missing values explicitly (don't silently drop)
- Use method chaining for readability
- Validate data quality before and after transformations
- Use `.copy()` when modifying subsets

### MUST NOT DO
- Iterate over DataFrame rows with `.iterrows()` unless absolutely necessary
- Use chained indexing (`df['A']['B']`) — use `.loc[]` or `.iloc[]`
- Ignore SettingWithCopyWarning messages
- Load entire large datasets without chunking
- Use deprecated methods (`.ix`, `.append()` — use `pd.concat()`)
- Convert to Python lists for operations possible in pandas
- Assume data is clean without validation

## Output Templates

When implementing pandas solutions, provide:
1. Code with vectorized operations and proper indexing
2. Comments explaining complex transformations
3. Memory/performance considerations if dataset is large
4. Data validation checks (dtypes, nulls, shapes)
