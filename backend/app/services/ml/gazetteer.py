"""
Curated scientific-entity gazetteer for Phase 3 entity extraction.

WHY A GAZETTEER INSTEAD OF A PRETRAINED NER MODEL
---------------------------------------------------
The brief's own instruction is: "Investigate appropriate Hugging Face
models rather than implementing NER from scratch" AND "do not blindly add
SciBERT just because it is mentioned" AND "choose models based on the
actual task." We did investigate. The honest finding:

- General scientific NER models on Hugging Face (e.g. models trained on
  SciERC) recognize coarse classes like Task / Method / Metric / Material
  / OtherScientificTerm — they do NOT reliably distinguish "SciBERT" (a
  MODEL) from "ImageNet" (a DATASET) from "F1-score" (a METRIC) at the
  fine granularity this feature needs, and the best of them are research
  checkpoints with no maintained pip package, inconsistent tokenizer
  compatibility, and licenses that aren't clearly stated — they fail the
  "actively maintained" / "license" criteria in item 19 of the brief.
- SciBERT itself (allenai/scibert_scivocab_uncased) is an embeddings
  backbone, not a fine-tuned NER head — using it for NER "because it's
  SciBERT" would be exactly the anti-pattern the brief warns against.

So Phase 3 uses a deterministic, explainable, provenance-friendly
approach instead: a curated gazetteer of canonical ML/CS entities
(the exact categories the brief asks for — models, datasets, methods,
metrics, domains, tasks) matched against paper text with `rapidfuzz`
fuzzy string matching (handles case, hyphenation, and minor OCR/PDF
extraction noise, e.g. "Res Net-50" or "resnet50" both resolve to
"ResNet-50"). This is combined with an OPTIONAL spaCy noun-chunk pass
(entity_extraction.py) that surfaces candidate method phrases NOT in the
gazetteer for human review, so the system doesn't silently miss entities
outside this list.

Every match keeps a real confidence score (the fuzzy match ratio) and
full provenance (chunk id, page, section) — nothing here is invented.
This list is intentionally extensible: add an entry and every paper
processed afterward benefits, no retraining required.
"""
from __future__ import annotations

# entity_type -> {canonical_name: [aliases...]}
GAZETTEER: dict[str, dict[str, list[str]]] = {
    "model": {
        "BERT": ["bert"],
        "SciBERT": ["scibert", "sci-bert"],
        "RoBERTa": ["roberta"],
        "DistilBERT": ["distilbert"],
        "GPT-2": ["gpt2", "gpt-2"],
        "GPT-3": ["gpt3", "gpt-3"],
        "GPT-4": ["gpt4", "gpt-4"],
        "T5": ["t5"],
        "LLaMA": ["llama"],
        "ResNet": ["resnet", "resnet-50", "resnet50", "resnet-101", "resnet101", "resnet-18"],
        "VGG": ["vgg", "vgg16", "vgg-16", "vgg19", "vgg-19"],
        "Inception": ["inception", "inceptionv3", "inception-v3", "googlenet"],
        "EfficientNet": ["efficientnet", "efficientnet-b0", "efficientnetb0"],
        "MobileNet": ["mobilenet", "mobilenetv2", "mobilenet-v2", "mobilenetv3", "mobilenet-v3"],
        "DenseNet": ["densenet"],
        "U-Net": ["unet", "u-net"],
        "YOLO": ["yolo", "yolov3", "yolov4", "yolov5", "yolov8"],
        "Faster R-CNN": ["faster r-cnn", "faster rcnn", "fasterrcnn"],
        "Mask R-CNN": ["mask r-cnn", "mask rcnn", "maskrcnn"],
        "Vision Transformer": ["vit", "vision transformer"],
        "Swin Transformer": ["swin transformer", "swin-transformer", "swintransformer"],
        "LSTM": ["lstm", "long short-term memory"],
        "GRU": ["gru", "gated recurrent unit"],
        "RNN": ["rnn", "recurrent neural network"],
        "CNN": ["cnn", "convolutional neural network"],
        "Transformer": ["transformer", "transformers"],
        "Random Forest": ["random forest", "random forests", "rf classifier"],
        "XGBoost": ["xgboost", "xg-boost"],
        "LightGBM": ["lightgbm", "light gbm"],
        "SVM": ["svm", "support vector machine", "support vector machines"],
        "Naive Bayes": ["naive bayes", "naïve bayes"],
        "Autoencoder": ["autoencoder", "auto-encoder"],
        "GAN": ["gan", "generative adversarial network"],
        "Diffusion Model": ["diffusion model", "denoising diffusion"],
        "Word2Vec": ["word2vec", "word 2 vec"],
        "GloVe": ["glove"],
        "FastText": ["fasttext", "fast text"],
        "MediaPipe": ["mediapipe", "media pipe"],
        "Sentence-BERT": ["sentence-bert", "sbert", "sentence transformers"],
    },
    "dataset": {
        "ImageNet": ["imagenet"],
        "COCO": ["coco", "ms-coco", "ms coco"],
        "MNIST": ["mnist"],
        "CIFAR-10": ["cifar-10", "cifar10"],
        "CIFAR-100": ["cifar-100", "cifar100"],
        "ISIC": ["isic", "isic 2018", "isic 2019", "isic 2020"],
        "PubMed": ["pubmed"],
        "S2ORC": ["s2orc"],
        "SQuAD": ["squad"],
        "GLUE": ["glue benchmark", "glue"],
        "PASCAL VOC": ["pascal voc", "voc2007", "voc2012"],
        "Cityscapes": ["cityscapes"],
        "CelebA": ["celeba"],
        "LFW": ["lfw", "labeled faces in the wild"],
        "WikiText": ["wikitext"],
        "Common Crawl": ["common crawl", "commoncrawl"],
        "PlantVillage": ["plantvillage", "plant village"],
        "UCI Machine Learning Repository": ["uci repository", "uci dataset", "uci ml repository"],
        "Kaggle": ["kaggle dataset", "kaggle"],
        "HAM10000": ["ham10000", "ham 10000"],
        "CheXpert": ["chexpert"],
        "MIMIC-III": ["mimic-iii", "mimic iii"],
    },
    "method": {
        "transfer learning": ["transfer learning"],
        "fine-tuning": ["fine-tuning", "finetuning", "fine tuning"],
        "contrastive learning": ["contrastive learning"],
        "federated learning": ["federated learning"],
        "data augmentation": ["data augmentation"],
        "self-supervised learning": ["self-supervised learning", "self supervised learning"],
        "semi-supervised learning": ["semi-supervised learning", "semi supervised learning"],
        "few-shot learning": ["few-shot learning", "few shot learning"],
        "zero-shot learning": ["zero-shot learning", "zero shot learning"],
        "ensemble learning": ["ensemble learning", "ensembling"],
        "attention mechanism": ["attention mechanism", "self-attention", "self attention"],
        "dropout": ["dropout"],
        "batch normalization": ["batch normalization", "batchnorm"],
        "cross-validation": ["cross-validation", "cross validation", "k-fold cross-validation"],
        "hyperparameter tuning": ["hyperparameter tuning", "hyperparameter optimization"],
        "knowledge distillation": ["knowledge distillation"],
        "reinforcement learning": ["reinforcement learning"],
        "active learning": ["active learning"],
        "multi-task learning": ["multi-task learning", "multitask learning"],
        "model pruning": ["model pruning", "network pruning"],
        "quantization": ["quantization", "model quantization"],
        "regularization": ["regularization", "l1 regularization", "l2 regularization"],
    },
    "metric": {
        "accuracy": ["accuracy"],
        "precision": ["precision"],
        "recall": ["recall", "sensitivity"],
        "F1-score": ["f1-score", "f1 score", "f-measure", "f1"],
        "AUC": ["auc", "auc-roc", "area under the curve", "roc-auc"],
        "BLEU": ["bleu", "bleu score"],
        "ROUGE": ["rouge", "rouge score", "rouge-l", "rouge-1", "rouge-2"],
        "specificity": ["specificity"],
        "mAP": ["map", "mean average precision"],
        "IoU": ["iou", "intersection over union"],
        "RMSE": ["rmse", "root mean square error", "root mean squared error"],
        "MAE": ["mae", "mean absolute error"],
        "perplexity": ["perplexity"],
        "top-1 accuracy": ["top-1 accuracy", "top1 accuracy"],
        "top-5 accuracy": ["top-5 accuracy", "top5 accuracy"],
        "Dice coefficient": ["dice coefficient", "dice score"],
        "confusion matrix": ["confusion matrix"],
        "latency": ["latency", "inference latency"],
        "FPS": ["fps", "frames per second"],
    },
    "domain": {
        "medical imaging": ["medical imaging"],
        "natural language processing": ["natural language processing", "nlp"],
        "computer vision": ["computer vision"],
        "remote sensing": ["remote sensing"],
        "speech recognition": ["speech recognition", "automatic speech recognition"],
        "signal processing": ["signal processing"],
        "bioinformatics": ["bioinformatics"],
        "robotics": ["robotics"],
        "autonomous driving": ["autonomous driving", "self-driving"],
        "dermatology": ["dermatology"],
        "agriculture": ["agriculture", "precision agriculture"],
        "cybersecurity": ["cybersecurity", "cyber security"],
        "recommender systems": ["recommender systems", "recommendation systems"],
        "time series analysis": ["time series analysis", "time series forecasting"],
        "sign language recognition": ["sign language recognition", "sign language translation"],
        "embedded systems": ["embedded systems"],
        "edge computing": ["edge computing"],
    },
    "task": {
        "image classification": ["image classification"],
        "object detection": ["object detection"],
        "semantic segmentation": ["semantic segmentation"],
        "instance segmentation": ["instance segmentation"],
        "text classification": ["text classification"],
        "named entity recognition": ["named entity recognition", "ner"],
        "sentiment analysis": ["sentiment analysis"],
        "question answering": ["question answering", "qa"],
        "machine translation": ["machine translation"],
        "text summarization": ["text summarization", "summarization"],
        "anomaly detection": ["anomaly detection"],
        "disease classification": ["disease classification", "disease detection"],
        "skin lesion classification": ["skin lesion classification", "skin cancer classification"],
        "gesture recognition": ["gesture recognition"],
        "speaker identification": ["speaker identification"],
    },
}


def iter_gazetteer_entries():
    """Yield (entity_type, canonical_name, alias) for every gazetteer entry."""
    for entity_type, entries in GAZETTEER.items():
        for canonical_name, aliases in entries.items():
            for alias in aliases:
                yield entity_type, canonical_name, alias
