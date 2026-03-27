# ⚡ EV Market Analysis (Europe) — Notebook + Interactive Dashboard (COP4283 Final Project)

## 1) Project Summary
This project is an end-to-end data exploration and visualization of the electric vehicle (EV) market with a **Europe-only focus**. It connects **EV specifications + pricing** with **charging station infrastructure** to study the trade-offs between:

- **Innovation** (range, battery size, fast charging, performance)
- **Affordability** (value metrics beyond sticker price)
- **Adoption readiness** (charging cost, capacity, usage, installation trends)

Deliverables included:
- `notebook_europe.ipynb` (full workflow + narrative + charts)
- `app_fixed.py` (Streamlit interactive dashboard)

---

## 2) Team
**Made by:** Krish Maisuria, Dev Shah, Miykle Ahmed, Felipe Serna

---

## 3) Research Questions
1. **Innovation vs Affordability:** How do range, battery, fast charging, and performance relate to EV price (EUR)?
2. **Best value models/brands:** Which EVs provide the best value using metrics like **€/km of range** and **€/kWh**?
3. **Infrastructure patterns (Europe):** How do charging station costs, capacity, and usage differ across charger types in Europe?
4. **Combined insight:** Using EV efficiency and typical European charging price, what is an estimated **energy cost per 100 km (EUR)**?

---

## 4) Datasets
This project uses **two CSV datasets**:

1. **EV models dataset**: `EV_cars.csv`  
   Contains EV model-level specs and price info (battery, range, efficiency, fast charge, acceleration, etc.).  
   Prices are treated as **EUR** in this project.

2. **Charging station dataset**: `detailed_ev_charging_stations.csv`  
   Contains station attributes (charger type, cost per kWh, capacity (kW), usage/day, installation year, lat/lon, etc.).  
   Raw pricing is provided as **USD/kWh** in the dataset.

Place both files in the `data/` folder.

---

## 5) Folder Structure

```text
COP4283FinalProject/
├── README.md
├── requirements.txt
├── notebook_europe.ipynb
├── app_fixed.py
├── data/
│   ├── EV_cars.csv
│   └── detailed_ev_charging_stations.csv
├── outputs/   # optional
│   ├── ev_cleaned.csv
│   └── stations_cleaned.csv
