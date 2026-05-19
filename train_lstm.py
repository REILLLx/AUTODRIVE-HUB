import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_error, r2_score
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping
import joblib

print("📂 Завантаження датасету...")
df = pd.read_csv('synthetic_ev_data_train.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values(['vehicle_id', 'timestamp']).reset_index(drop=True)

df = df[~df['vehicle_id'].isin(['Tesla_01', 'Hyundai_02'])].reset_index(drop=True)
print(f"✅ Після фільтрації: {len(df)} рядків | авто: {list(df['vehicle_id'].unique())}")

FEATURES    = ['soc_pct', 'vehicle_speed_kph', 'battery_temp_c']
WINDOW_SIZE = 40
HORIZON     = 120
SPLIT_RATIO = 0.8

all_train_raw = []
vehicle_splits = {}

for vid, group in df.groupby('vehicle_id'):
    data = group[FEATURES].values
    split_idx = int(len(data) * SPLIT_RATIO)
    vehicle_splits[vid] = {
        'train': data[:split_idx],
        'test':  data[split_idx:],
    }
    all_train_raw.append(data[:split_idx])

scaler = MinMaxScaler(feature_range=(0, 1))
scaler.fit(np.vstack(all_train_raw))
joblib.dump(scaler, 'scaler.gz')

soc_min = scaler.data_min_[0]
soc_max = scaler.data_max_[0]
print(f"💾 Скалер збережено: scaler.gz")
print(f"   SOC діапазон: {soc_min:.1f}% – {soc_max:.1f}%")


def create_sequences(data_scaled, window, horizon):
    X, y = [], []
    for i in range(window, len(data_scaled) - horizon):
        X.append(data_scaled[i - window:i])
        y.append(data_scaled[i + horizon, 0])
    return np.array(X), np.array(y)


all_X_train, all_y_train = [], []
all_X_test,  all_y_test  = [], []

for vid, splits in vehicle_splits.items():
    train_scaled = scaler.transform(splits['train'])
    test_scaled  = scaler.transform(splits['test'])

    X_tr, y_tr = create_sequences(train_scaled, WINDOW_SIZE, HORIZON)
    X_te, y_te = create_sequences(test_scaled,  WINDOW_SIZE, HORIZON)

    if len(X_tr) == 0 or len(X_te) == 0:
        print(f"  ⚠️  {vid}: недостатньо даних, пропускаємо")
        continue

    all_X_train.append(X_tr)
    all_y_train.append(y_tr)
    all_X_test.append(X_te)
    all_y_test.append(y_te)

    print(f"  {vid}: train={len(X_tr)} вікон | test={len(X_te)} вікон")

X_train = np.vstack(all_X_train)
y_train = np.concatenate(all_y_train)
X_test  = np.vstack(all_X_test)
y_test  = np.concatenate(all_y_test)

print(f"\n📊 X_train={X_train.shape} | X_test={X_test.shape}")
print(f"   Вікно: {WINDOW_SIZE} кроків ({WINDOW_SIZE*30//60} хв) → прогноз через {HORIZON} кроків ({HORIZON*30//60} хв)")


model = Sequential([
    LSTM(64, return_sequences=True,
         input_shape=(WINDOW_SIZE, len(FEATURES))),
    Dropout(0.2),
    LSTM(32),
    Dropout(0.2),
    Dense(1),
])
model.compile(optimizer='adam', loss='mse', metrics=['mae'])
model.summary()


print(f"\n🧠 Навчання на {len(X_train)} вікнах...")

early_stop = EarlyStopping(
    monitor='val_loss',
    patience=4,
    restore_best_weights=True,
    verbose=1,
)

history = model.fit(
    X_train, y_train,
    epochs=30,
    batch_size=32,
    validation_data=(X_test, y_test),
    callbacks=[early_stop],
    verbose=1,
)


predictions = model.predict(X_test, verbose=0)
mae = mean_absolute_error(y_test, predictions)
r2  = r2_score(y_test, predictions)

dummy      = np.zeros((len(predictions), len(FEATURES)))
dummy[:,0] = predictions[:,0]
pred_real  = scaler.inverse_transform(dummy)[:,0]

dummy2      = np.zeros((len(y_test), len(FEATURES)))
dummy2[:,0] = y_test
real_soc    = scaler.inverse_transform(dummy2)[:,0]

mae_real = mean_absolute_error(real_soc, pred_real)

print("\n" + "="*50)
print("📈 РЕЗУЛЬТАТИ:")
print(f"   MAE (нормалізований):  {mae:.5f}")
print(f"   MAE (реальний SOC %):  {mae_real:.3f}%")
print(f"   R² Score:              {r2:.5f}")
print(f"   Прогноз на:            1 година вперед")
print("="*50)


fig, axes = plt.subplots(1, 2, figsize=(14, 5))

axes[0].plot(history.history['loss'],     label='Train Loss (MSE)')
axes[0].plot(history.history['val_loss'], label='Val Loss (MSE)')
axes[0].set_title('Процес навчання LSTM')
axes[0].set_xlabel('Епоха')
axes[0].set_ylabel('Loss (MSE)')
axes[0].legend()
axes[0].grid(True, alpha=0.3)

vw      = df[df['vehicle_id'] == 'VW_01'].copy()
vw_data = vw[FEATURES].values
split_vw    = int(len(vw_data) * SPLIT_RATIO)
vw_test_raw = vw_data[split_vw:]
vw_scaled   = scaler.transform(vw_test_raw)
X_vis, y_vis = create_sequences(vw_scaled, WINDOW_SIZE, HORIZON)

if len(X_vis) > 0:
    pred_vis = model.predict(X_vis, verbose=0)

    dummy_vis      = np.zeros((len(pred_vis), len(FEATURES)))
    dummy_vis[:,0] = pred_vis[:,0]
    pred_soc_vis   = scaler.inverse_transform(dummy_vis)[:,0]

    dummy_vis2      = np.zeros((len(y_vis), len(FEATURES)))
    dummy_vis2[:,0] = y_vis
    real_soc_vis    = scaler.inverse_transform(dummy_vis2)[:,0]

    n_show = min(300, len(real_soc_vis))
    axes[1].plot(real_soc_vis[:n_show],  label='Реальний SOC через 1 год',
                 linewidth=1.5, alpha=0.9)
    axes[1].plot(pred_soc_vis[:n_show],  label='Прогноз LSTM',
                 linewidth=1.5, alpha=0.9, linestyle='--')
    axes[1].set_title(f'VW_01 (test set): Прогноз на 1 год вперед\n'
                      f'MAE = {mae_real:.2f}%,  R² = {r2:.4f}')
    axes[1].set_xlabel('Крок (тестова вибірка)')
    axes[1].set_ylabel('SOC (%)')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('learning_curve.png', dpi=150)
print("📈 Графік збережено: learning_curve.png")


model.save('ev_model.keras')
print("💾 Модель збережено: ev_model.keras")
print(f"\n✅ Готово. Модель прогнозує SOC через 1 годину.")
print(f"   В receiver.py встанови: порог=40, reshape=(1, 40, 3)")
