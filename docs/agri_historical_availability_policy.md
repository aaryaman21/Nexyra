# Historical price availability policy

The Kaggle annual files contain observation dates but no publication or first-seen timestamps. Ingestion therefore stores `verified_available_at = NULL` and `availability_status = "unknown"`. It never substitutes download time or observation date. These rows live only in `agri_historical_price_observations`; the production price loader, forecast endpoints, and model registry continue to read the canonical table.

For explicitly labeled retrospective research only, an experiment may select a conservative assumed availability policy. The default policy is **seven calendar days after the observation date**, at the end of that day in Asia/Kolkata. This lag is a sensitivity assumption, not evidence about actual publication time, and must be reported with experiment results. Researchers should also report sensitivity to longer delays. The assumption must not be written into `verified_available_at` or presented as leakage-safe real-time history.

Future semantic/news features may be joined only using genuine source `published_at` and `available_at` timestamps, with both no later than the simulated forecast cutoff. Unknown article availability excludes the feature. Historical price data alone does not establish historical availability for news or other semantic features.

No model training is authorized by this ingestion. A later research/evaluation path must explicitly opt into the policy, remain separate from live inference, preserve exact market/variety/grade identities, and use chronological train/calibration/validation/test splits.
