"""
Forecast Model Performance Analysis Script

Analyzes ensemble forecast performance across all services and metrics.
Generates comprehensive report with:
- MAPE/MAE/RMSE statistics
- Fallback rates
- Per-model performance comparison
- Recommendations for improvement
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from backend.database import SessionLocal
from backend import models
from sqlalchemy import func, desc
import statistics
from collections import defaultdict
from datetime import datetime, timedelta

db = SessionLocal()

# Query all forecast result tables
tables = [
    ('ec2', models.EC2ForecastResult),
    ('rds', models.RDSForecastResult),
    ('lambda', models.LambdaForecastResult),
    ('s3', models.S3ForecastResult),
    ('alb', models.ALBForecastResult),
]

print("=" * 80)
print("FORECAST MODEL PERFORMANCE ANALYSIS")
print("=" * 80)
print()

# Collect all results
all_results = []
for service_name, model_class in tables:
    # Get recent results (last 7 days)
    cutoff = datetime.utcnow() - timedelta(days=7)
    rows = db.query(model_class).filter(
        model_class.created_at >= cutoff
    ).order_by(desc(model_class.created_at)).all()
    
    for row in rows:
        all_results.append({
            'service': service_name,
            'metric': row.metric,
            'method': row.method,
            'mae': row.mae,
            'rmse': row.rmse,
            'mape': row.mape,
            'has_backtest': row.backtest_dates is not None and len(row.backtest_dates or []) > 0,
            'forecast_length': len(row.forecast_values) if row.forecast_values else 0,
            'has_costs': row.forecast_costs is not None and len(row.forecast_costs or []) > 0,
            'created_at': row.created_at,
        })

db.close()

if not all_results:
    print("No forecast results found in the last 7 days.")
    print("Run some forecasts first to generate performance data.")
    sys.exit(0)

print(f"Total forecasts analyzed: {len(all_results)}")
print(f"Date range: {min(r['created_at'] for r in all_results).strftime('%Y-%m-%d %H:%M')} to {max(r['created_at'] for r in all_results).strftime('%Y-%m-%d %H:%M')}")
print()

# ─── 1. Overall Performance Metrics ───────────────────────────────────
print("=" * 80)
print("1. OVERALL PERFORMANCE METRICS")
print("=" * 80)

results_with_metrics = [r for r in all_results if r['mape'] is not None]
if results_with_metrics:
    mapes = [r['mape'] for r in results_with_metrics]
    maes = [r['mae'] for r in results_with_metrics if r['mae'] is not None]
    rmses = [r['rmse'] for r in results_with_metrics if r['rmse'] is not None]
    
    print(f"\nMAPE (Mean Absolute Percentage Error):")
    print(f"  Mean:   {statistics.mean(mapes):.2f}%")
    print(f"  Median: {statistics.median(mapes):.2f}%")
    print(f"  Min:    {min(mapes):.2f}%")
    print(f"  Max:    {max(mapes):.2f}%")
    print(f"  StdDev: {statistics.stdev(mapes) if len(mapes) > 1 else 0:.2f}%")
    
    if maes:
        print(f"\nMAE (Mean Absolute Error):")
        print(f"  Mean:   {statistics.mean(maes):.4f}")
        print(f"  Median: {statistics.median(maes):.4f}")
    
    if rmses:
        print(f"\nRMSE (Root Mean Squared Error):")
        print(f"  Mean:   {statistics.mean(rmses):.4f}")
        print(f"  Median: {statistics.median(rmses):.4f}")
else:
    print("\nNo performance metrics available (all forecasts may have failed)")

# ─── 2. Per-Service Performance ──────────────────────────────────────
print("\n" + "=" * 80)
print("2. PER-SERVICE PERFORMANCE")
print("=" * 80)

by_service = defaultdict(list)
for r in results_with_metrics:
    by_service[r['service']].append(r)

for service in sorted(by_service.keys()):
    service_results = by_service[service]
    mapes = [r['mape'] for r in service_results]
    
    print(f"\n{service.upper()}:")
    print(f"  Forecasts: {len(service_results)}")
    print(f"  Avg MAPE:  {statistics.mean(mapes):.2f}%")
    print(f"  Med MAPE:  {statistics.median(mapes):.2f}%")
    print(f"  Min MAPE:  {min(mapes):.2f}%")
    print(f"  Max MAPE:  {max(mapes):.2f}%")

# ─── 3. Per-Metric Performance ───────────────────────────────────────
print("\n" + "=" * 80)
print("3. PER-METRIC PERFORMANCE")
print("=" * 80)

by_metric = defaultdict(list)
for r in results_with_metrics:
    key = f"{r['service']}/{r['metric']}"
    by_metric[key].append(r)

# Sort by average MAPE
metric_stats = []
for metric_key in by_metric:
    metric_results = by_metric[metric_key]
    mapes = [r['mape'] for r in metric_results]
    metric_stats.append({
        'metric': metric_key,
        'count': len(metric_results),
        'avg_mape': statistics.mean(mapes),
        'med_mape': statistics.median(mapes),
    })

metric_stats.sort(key=lambda x: x['avg_mape'])

print("\nBest Performing Metrics (lowest MAPE):")
for stat in metric_stats[:5]:
    print(f"  {stat['metric']:40s} → Avg MAPE: {stat['avg_mape']:6.2f}% (n={stat['count']})")

print("\nWorst Performing Metrics (highest MAPE):")
for stat in metric_stats[-5:]:
    print(f"  {stat['metric']:40s} → Avg MAPE: {stat['avg_mape']:6.2f}% (n={stat['count']})")

# ─── 4. Method Analysis (Ensemble vs Fallback) ───────────────────────
print("\n" + "=" * 80)
print("4. METHOD ANALYSIS")
print("=" * 80)

by_method = defaultdict(list)
for r in all_results:
    by_method[r['method']].append(r)

for method in sorted(by_method.keys()):
    method_results = by_method[method]
    with_metrics = [r for r in method_results if r['mape'] is not None]
    
    print(f"\n{method.upper()}:")
    print(f"  Total forecasts: {len(method_results)}")
    if with_metrics:
        mapes = [r['mape'] for r in with_metrics]
        print(f"  Avg MAPE:        {statistics.mean(mapes):.2f}%")
        print(f"  Med MAPE:        {statistics.median(mapes):.2f}%")

# Calculate fallback rate
ensemble_count = len([r for r in all_results if 'ensemble' in r['method'].lower()])
fallback_count = len([r for r in all_results if 'moving_average' in r['method'].lower() or 'fallback' in r['method'].lower()])
total_count = len(all_results)

print(f"\nFallback Rate:")
print(f"  Ensemble:       {ensemble_count:4d} ({ensemble_count/total_count*100:.1f}%)")
print(f"  Fallback:       {fallback_count:4d} ({fallback_count/total_count*100:.1f}%)")

# ─── 5. Backtest Coverage ────────────────────────────────────────────
print("\n" + "=" * 80)
print("5. BACKTEST COVERAGE")
print("=" * 80)

with_backtest = [r for r in all_results if r['has_backtest']]
print(f"\nForecasts with backtest: {len(with_backtest)}/{len(all_results)} ({len(with_backtest)/len(all_results)*100:.1f}%)")

# ─── 6. Cost Integration ─────────────────────────────────────────────
print("\n" + "=" * 80)
print("6. COST INTEGRATION")
print("=" * 80)

with_costs = [r for r in all_results if r['has_costs']]
print(f"\nForecasts with cost data: {len(with_costs)}/{len(all_results)} ({len(with_costs)/len(all_results)*100:.1f}%)")

# ─── 7. MAPE Distribution ────────────────────────────────────────────
print("\n" + "=" * 80)
print("7. MAPE DISTRIBUTION")
print("=" * 80)

if results_with_metrics:
    mapes = [r['mape'] for r in results_with_metrics]
    
    buckets = [
        ("Excellent (<10%)", lambda m: m < 10),
        ("Good (10-20%)", lambda m: 10 <= m < 20),
        ("Fair (20-30%)", lambda m: 20 <= m < 30),
        ("Poor (30-50%)", lambda m: 30 <= m < 50),
        ("Very Poor (≥50%)", lambda m: m >= 50),
    ]
    
    print()
    for label, condition in buckets:
        count = len([m for m in mapes if condition(m)])
        pct = count / len(mapes) * 100
        bar = "█" * int(pct / 2)
        print(f"  {label:20s} {count:4d} ({pct:5.1f}%) {bar}")

# ─── 8. Recommendations ──────────────────────────────────────────────
print("\n" + "=" * 80)
print("8. RECOMMENDATIONS")
print("=" * 80)

recommendations = []

if results_with_metrics:
    avg_mape = statistics.mean([r['mape'] for r in results_with_metrics])
    
    if avg_mape > 30:
        recommendations.append(
            "⚠️  High average MAPE (>30%) - Consider:\n"
            "   • Increase training data window\n"
            "   • Review data quality and outliers\n"
            "   • Adjust seasonal period detection"
        )
    elif avg_mape < 15:
        recommendations.append(
            "✅ Excellent average MAPE (<15%) - Models performing well"
        )
    
    if fallback_count / total_count > 0.3:
        recommendations.append(
            "⚠️  High fallback rate (>30%) - Consider:\n"
            "   • Increase adaptive MAPE thresholds\n"
            "   • Improve data preprocessing\n"
            "   • Add more training data"
        )
    
    # Check for metrics with consistently high MAPE
    high_mape_metrics = [s for s in metric_stats if s['avg_mape'] > 50]
    if high_mape_metrics:
        recommendations.append(
            f"⚠️  {len(high_mape_metrics)} metrics with MAPE >50% - Review:\n" +
            "\n".join(f"   • {m['metric']}" for m in high_mape_metrics[:3])
        )
    
    if len(with_backtest) / len(all_results) < 0.5:
        recommendations.append(
            "ℹ️  Low backtest coverage (<50%) - Enable backtesting for better validation"
        )

if recommendations:
    print()
    for rec in recommendations:
        print(rec)
        print()
else:
    print("\n✅ No major issues detected. Models are performing as expected.")

print("=" * 80)
print("END OF REPORT")
print("=" * 80)
