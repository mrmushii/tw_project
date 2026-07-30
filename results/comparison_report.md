# Agent (Claude API) vs VGG-16 — Comparison Report

Both branches evaluated on the **same 216 test images**.

## Headline metrics

| Branch | Accuracy | Macro-F1 |
|---|---|---|
| Agent (Claude API) | 0.917 | 0.916 |
| VGG-16 (fine-tuned) | 0.903 | 0.903 |

## Confusion matrices

![Confusion matrices](confusion_matrices.png)

## Per-class report — Agent (Claude API)

```
              precision    recall  f1-score   support

   buildings      1.000     0.778     0.875        36
      forest      0.947     1.000     0.973        36
     glacier      0.968     0.833     0.896        36
    mountain      0.829     0.944     0.883        36
         sea      1.000     0.944     0.971        36
      street      0.818     1.000     0.900        36

    accuracy                          0.917       216
   macro avg      0.927     0.917     0.916       216
weighted avg      0.927     0.917     0.916       216

```

## Per-class report — VGG-16 (fine-tuned)

```
              precision    recall  f1-score   support

   buildings      0.875     0.972     0.921        36
      forest      0.972     0.972     0.972        36
     glacier      0.784     0.806     0.795        36
    mountain      0.861     0.861     0.861        36
         sea      0.971     0.944     0.958        36
      street      0.969     0.861     0.912        36

    accuracy                          0.903       216
   macro avg      0.905     0.903     0.903       216
weighted avg      0.905     0.903     0.903       216

```

## Disagreements to spot-check

Images where the two branches predicted different classes (open a few by eye to judge which answer is more reasonable):

| image | true | agent | vgg-16 |
|---|---|---|---|
| buildings_11428.jpg | buildings | street | buildings |
| buildings_11570.jpg | buildings | street | buildings |
| buildings_12684.jpg | buildings | street | buildings |
| buildings_18456.jpg | buildings | street | buildings |
| buildings_318.jpg | buildings | street | buildings |
| buildings_7877.jpg | buildings | street | buildings |
| buildings_8390.jpg | buildings | street | buildings |
| forest_16427.jpg | forest | forest | glacier |
| glacier_17042.jpg | glacier | glacier | mountain |
| glacier_3759.jpg | glacier | mountain | glacier |
| glacier_5494.jpg | glacier | glacier | sea |
| glacier_6055.jpg | glacier | mountain | glacier |
| glacier_7721.jpg | glacier | mountain | forest |
| glacier_8641.jpg | glacier | glacier | mountain |
| mountain_11402.jpg | mountain | mountain | glacier |
