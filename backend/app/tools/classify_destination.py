# backend/app/tools/classify_destination.py
import asyncio
import pandas as pd
from app.models.schemas import ClassifyInput, ClassifyOutput
from app.services.features import compute_features


async def classify_destination(input: ClassifyInput, classifier) -> ClassifyOutput:
    """
    Classify a single destination. If 'features' is not provided directly,
    compute features live from the internet using the destination name.
    """
    # If a destination name was provided via the agent, compute features live
    # (The agent now passes a destination name string via the classify tool)
    features_model = input.features  # already a DestinationFeatures

    df = pd.DataFrame([features_model.model_dump()])
    pred = await asyncio.to_thread(classifier.predict, df)
    proba = await asyncio.to_thread(classifier.predict_proba, df)
    classes = classifier.classes_
    return ClassifyOutput(
        label=pred[0],
        probabilities={cls: float(p) for cls, p in zip(classes, proba[0])},
    )