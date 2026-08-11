# Guía Rápida - CSIRO Biomass Prediction

Esta guía detalla cómo configurar y ejecutar el proyecto localmente.

## 1. Configuración del Token de Hugging Face
Para descargar los pesos o inicializar el modelo por primera vez, necesitas un token de Hugging Face. Tienes dos formas de usarlo:

### Opción A: Como argumento en el script de descarga
```bash
python download_weights.py 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
```

### Opción B: Como variable de entorno (Recomendado)
En la terminal de Windows (PowerShell o CMD), ejecuta:
```powershell
$env:HF_TOKEN="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"
```
O en CMD:
```cmd
set HF_TOKEN=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
```

## 2. Pesos del Backbone
Ya hemos descargado los pesos en la carpeta:
`./backbone_weights/`

En caso de no estar en la carpeta ejecutar download_weights.py

El código está configurado para buscar primero en esta carpeta local antes de intentar descargar de internet.

## 3. Entrenamiento e Inferencia

### Entrenamiento
- **Archivo**: `train.py`
- **Ejecución**: `python train.py`
- **Resultados**: Los pesos se guardan en `./checkpoints/ver0/fold_X/best_ema.bin`.

### Inferencia
- **Archivo**: `predict.py`
- **Ejecución**: `python predict.py --csv test_wide.csv --weights_dir ./checkpoints/ver0`
- **Funcionamiento**: El script leerá los mejores pesos encontrados en la carpeta de checkpoints para generar el archivo `submission.csv`.

## 4. Estructura de Trabajo

| Paso | Script | Acción | Resultado |
| :--- | :--- | :--- | :--- |
| **1** | `prepare_data.py` | Preparar CSVs | `train_wide.csv`, `test_wide.csv` |
| **2** | `download_weights.py`| Bajar backbone | `./backbone_weights/` |
| **3** | `train.py` | Entrenar | `./checkpoints/ver0/` |
| **4** | `predict.py` | Predecir | `submission.csv` |
