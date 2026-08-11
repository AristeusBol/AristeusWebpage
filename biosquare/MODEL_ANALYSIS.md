# Informe Técnico: Arquitectura y Flujo del Modelo CSIRO Biomass

Este documento proporciona una visión profunda de la arquitectura del modelo, el propósito de cada componente y el flujo operativo detallado, centrándose especialmente en la lógica de entrenamiento y selección de pesos.

---

## 1. Definiciones Conceptuales

*   **DINOv3 (Vision Transformer - ViT):** Es la "columna vertebral" (backbone). Divide la imagen en sectores y aplica "atención" para entender el contexto global de la vegetación.
*   **LoRA (Low-Rank Adaptation):** Técnica de ajuste fino eficiente. En lugar de mover todos los parámetros del Transformer, añade matrices pequeñas (r=32) que capturan la adaptación específica a la biomasa, manteniendo el conocimiento general del modelo base.
*   **Mamba (State Space Models):** Bloque de fusión espacial que integra eficientemente las dos vistas del par estéreo.
*   **Distribución Tweedie:** La biomasa suele tener muchos valores de cero y una cola larga de valores positivos. La función de pérdida Tweedie es ideal para este tipo de distribución estadística, superando al MSE tradicional.

---

## 2. Análisis de la Arquitectura (Nivel Pro)

1.  **Entrada Dual:** Se procesan dos imágenes simultáneamente (Cámara Izquierda y Derecha).
2.  **Backbone & LoRA:** Se extraen características con DINOv3-L/16. Los módulos `k_proj`, `v_proj`, `q_proj` y `o_proj` tienen adaptadores LoRA para optimizar la extracción de texturas vegetales.
3.  **Local Mamba Fusion:** 
    *   Suma los tokens de ambas cámaras.
    *   Usa convoluciones 1D (`dwconv`) para capturar relaciones locales entre parches.
    *   Usa un mecanismo de compuerta (`gate`) para decidir qué información es relevante.
4.  **Regresión Jerárquica Multi-objetivo:** El modelo predice tres valores raíz (Green, Dead, Clover) y utiliza capas `Softplus` para asegurar que las predicciones sean siempre positivas (la biomasa no puede ser negativa).

---

## 3. Guía de Archivos y sus Funciones

| Archivo | Función Técnica |
| :--- | :--- |
| `model.py` | Definición de la red, bloques LoRA (vía `peft`) y cabezales de regresión. |
| `dataset.py` | Pipeline de datos con aumentos de Albumentations. Escala los targets dividiendo por valores de referencia (max biomasa). |
| `train.py` | Orquestador del entrenamiento, gestión de épocas y Early Stopping. |
| `loss.py` | Implementa `TweedieLoss` (p=1.2). Esto permite que el modelo sea preciso tanto en suelos casi vacíos como en vegetación densa. |
| `metrics.py` | Calcula R2 ponderado. Da más peso al `Total` (0.5) y al `GDM` (0.2). |

---

## 4. El Proceso de Entrenamiento: Deep Dive

### A. Optimización Diferencial (`build_optimizer`)
El modelo utiliza diferentes velocidades de aprendizaje (Learning Rates) para distintas partes:
*   **Backbone:** 1e-4 (Muy lento, para no destruir el conocimiento pre-entrenado).
*   **Heads:** 1e-3 (Más rápido, para aprender la tarea de regresión desde cero).

### B. El Bucle de Entrenamiento (`_train`)
En cada paso (batch) ocurren varias cosas críticas:
1.  **Mixed Precision (Autocast):** Usa `bfloat16` para acelerar el cálculo y ahorrar memoria GPU.
2.  **Gradient Clipping:** Limita la norma de los gradientes a 1.0 para evitar que el entrenamiento "explote" si hay datos ruidosos.
3.  **EMA (Exponential Moving Average):** Se mantiene una copia "fantasma" del modelo. Sus pesos son un promedio móvil de los pesos actuales. Este modelo EMA suele ser mucho más estable frente al ruido y es el que se usa para la inferencia.

### C. Evaluación y Selección de los "Mejores Pesos" (`_eval` & `Balanced R2`)
El modelo no se guarda simplemente cuando tiene el error más bajo. Se usa una métrica inteligente llamada **Balanced R2 (BR2)**:
*   **Fórmula:** `Mean(R2_scores) - 0.1 * Std(R2_scores)`
*   **Por qué:** Penaliza al modelo si es muy bueno en una planta (ej. Green) pero malo en otra (ej. Clover). Fuerza al modelo a ser consistente en todos los componentes.
*   **Checkpointing:** Si el **BR2** mejora, se guarda como `best_ema.bin`.

### D. Early Stopping (Paciencia)
Si después de 20 épocas (parámetro `PATIENCE`) el BR2 no ha mejorado, el entrenamiento se detiene automáticamente para evitar el sobre-entrenamiento (Overfitting).

---

## 5. Ciclo de Vida del Modelo

1.  **Entrenamiento:** Ejecutas `train.py`. El modelo aprende y genera `best_ema.bin`.
2.  **Inferencia:** 
    *   **¡Ya no necesitas entrenar más!**
    *   Ejecutas `predict.py`.
    *   El script carga `best_ema.bin`.
    *   Aplica **TTA (Test Time Augmentation)**: voltea la imagen original y la de la cámara alterna para promediar resultados y reducir errores de perspectiva.

> [!IMPORTANT]
> El modelo utiliza **EMA (Exponential Moving Average)** durante el entrenamiento. Esto significa que guarda una versión "suavizada" de los pesos, que suele ser más estable y precisa para la inferencia. Por eso verás archivos llamados `best_ema.bin`.
