import csv
import matplotlib.pyplot as plt
import numpy as np

datos = []
with open("comparacion_real_vs_predicho.csv") as f:
    reader = csv.DictReader(f)
    for row in reader:
        datos.append(row)

atomicos = ["Dry_Clover_g", "Dry_Dead_g", "Dry_Green_g"]
colores = {"Dry_Clover_g": "#d4a017", "Dry_Dead_g": "#8b4513", "Dry_Green_g": "#2e8b57"}
labels = {"Dry_Clover_g": "Dry Clover (g)", "Dry_Dead_g": "Dry Dead (g)", "Dry_Green_g": "Dry Green (g)"}

fig, axes = plt.subplots(1, 3, figsize=(15, 5))

for ax, target in zip(axes, atomicos):
    real_col = f"{target}_real"
    pred_col = f"{target}_pred"

    real_vals = []
    pred_vals = []
    for row in datos:
        if row[real_col] != "Null" and row[pred_col] != "Null":
            real_vals.append(float(row[real_col]))
            pred_vals.append(float(row[pred_col]))

    real_vals = np.array(real_vals)
    pred_vals = np.array(pred_vals)

    n_puntos = len(real_vals)
    if n_puntos == 0:
        ax.set_title(f"{labels[target]} (sin datos)", fontsize=13, fontweight="bold")
        ax.grid(True, alpha=0.3)
        continue

    max_val = max(real_vals.max(), pred_vals.max()) * 1.05
    ax.plot([0, max_val], [0, max_val], "k--", lw=1, alpha=0.5, label="Identidad (y=x)")
    ax.scatter(real_vals, pred_vals, c=colores[target], edgecolors="black", alpha=0.7, s=60)

    for i in range(n_puntos):
        ax.plot([real_vals[i], real_vals[i]], [real_vals[i], pred_vals[i]],
                color="gray", lw=0.5, alpha=0.4)

    ax.set_xlabel("Real (g)", fontsize=11)
    ax.set_ylabel("Predicho (g)", fontsize=11)
    ax.set_title(f"{labels[target]} (n={n_puntos})", fontsize=13, fontweight="bold")
    ax.set_xlim(0, max_val)
    ax.set_ylim(0, max_val)
    ax.set_aspect("equal")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    r2 = 1 - np.sum((real_vals - pred_vals) ** 2) / np.sum((real_vals - real_vals.mean()) ** 2)
    mae = np.mean(np.abs(real_vals - pred_vals))
    rmse = np.sqrt(np.mean((real_vals - pred_vals) ** 2))
    ax.text(0.95, 0.05, f"$R^2$ = {r2:.3f}\nMAE = {mae:.2f}g\nRMSE = {rmse:.2f}g",
            transform=ax.transAxes, va="bottom", ha="right",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8), fontsize=9)

fig.suptitle("Real vs Predicho - Biomasa (g)", fontsize=15, fontweight="bold", y=1.02)
plt.tight_layout()
plt.savefig("real_vs_predicho.png", dpi=150, bbox_inches="tight")
print(f"Gráfico guardado como real_vs_predicho.png")
plt.show()
