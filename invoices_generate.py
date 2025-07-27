import os
import pandas as pd
import random
from faker import Faker
from datetime import datetime, timedelta
import numpy as np
from faker.providers import BaseProvider

# Création d'un provider custom pour les numéros de facture français
class InvoiceProvider(BaseProvider):
    def invoice_number(self, year):
        return f"FAC-{year}-{self.bothify(text='#####')}"

# Configuration
fake = Faker('fr_FR')
fake.add_provider(InvoiceProvider)
os.makedirs('invoices_output', exist_ok=True)

# Paramètres
NUM_INVOICES = 8000
CLIENT_IDS = list(range(1, 101))
CLIENT_TYPES = {cid: random.choice(['PUBLIC', 'PRIVE']) for cid in CLIENT_IDS}
STATUS_DISTRIBUTION = {
    'DRAFT': 0.1,
    'SENT': 0.3,
    'PAID': 0.4,
    'CANCELLED': 0.05,
    'OVERDUE': 0.15
}

# Fonctions de génération
def generate_invoice_base_data():
    invoice_date = fake.date_between(start_date='-2y', end_date='today')
    client_id = random.choice(CLIENT_IDS)
    client_type = CLIENT_TYPES[client_id]
    
    # Données de base
    quantity = random.randint(1, 20)
    pu = round(random.uniform(50, 2000), 2)
    total_ht = round(pu * quantity, 2)
    
    # Calculs spécifiques
    if client_type == "PUBLIC":
        montant_tva = round(total_ht * 0.2, 2)
        amount_ttc = round(total_ht * 1.2, 2)
        ras_5p = round(total_ht * 0.05, 2)
        ras_tva = round(total_ht * 0.2 * 0.75, 2)
        amount_to_pay = round(amount_ttc - ras_5p - ras_tva, 2)
    else:
        montant_tva = round(total_ht * 0.2, 2)
        amount_ttc = round(total_ht * 1.2, 2)
        ras_5p = 0
        ras_tva = 0
        amount_to_pay = amount_ttc
    
    return {
        'INVOICE_DATE': invoice_date,
        'CLIENT_ID': client_id,
        'CLIENT_TYPE': client_type,
        'TOTAL_HT': total_ht,
        'MONTANT_TVA': montant_tva,
        'AMOUNT_TTC': amount_ttc,
        'RAS_5P': ras_5p,
        'RAS_TVA': ras_tva,
        'AMOUNT_TO_PAY': amount_to_pay,
        'PU': pu,
        'QUANTITY': quantity,
        'ELECTRONIC_DATE': invoice_date + timedelta(days=random.randint(0, 2)),
        'PHYSICAL_DATE': invoice_date + timedelta(days=random.randint(1, 5)) if random.random() > 0.3 else None,
        'EXPECTED_PAYMENT_DATE': invoice_date + timedelta(days=random.randint(30, 90)),
        'LABEL': random.choice([
            "Développement logiciel", "Consulting IT", "Maintenance SaaS",
            "Formation technique", "Licence logicielle", "Hébergement cloud"
        ]),
        'PO': fake.bothify(text="PO-#####-??"),
        'INVOICE_YEAR': invoice_date.year
    }

def generate_all_invoices(num_invoices):
    invoices = []
    for _ in range(num_invoices):
        base_data = generate_invoice_base_data()
        status = random.choices(
            list(STATUS_DISTRIBUTION.keys()),
            weights=list(STATUS_DISTRIBUTION.values())
        )[0]
        
        payment_date = None
        if status == 'PAID':
            payment_date = base_data['EXPECTED_PAYMENT_DATE'] + timedelta(days=random.randint(-15, 15))
        
        invoice_data = {
            **base_data,
            'STATUS': status,
            'PAYMENT_DATE': payment_date,
            'INVOICE_NUMBER': fake.invoice_number(base_data['INVOICE_YEAR'])
        }
        invoices.append(invoice_data)
    
    return pd.DataFrame(invoices)

def split_invoices(df_invoices):
    # Factures payées (pour les transactions matched)
    paid_mask = df_invoices['STATUS'] == 'PAID'
    df_paid = df_invoices[paid_mask].copy()
    
    # Split en matched/unmatched/partial/grouped
    matched_count = int(len(df_paid) * 0.6)
    partial_count = int(len(df_paid) * 0.2)
    grouped_count = int(len(df_paid) * 0.15)
    
    matched = df_paid.iloc[:matched_count].copy()
    partial = df_paid.iloc[matched_count:matched_count+partial_count].copy()
    grouped = df_paid.iloc[matched_count+partial_count:matched_count+partial_count+grouped_count].copy()
    unmatched = df_paid.iloc[matched_count+partial_count+grouped_count:].copy()
    
    return {
        'matched': matched,
        'partial': partial,
        'grouped': grouped,
        'unmatched': unmatched,
        'non_paid': df_invoices[~paid_mask]
    }

def generate_bank_transactions(invoice_splits):
    transactions = []
    transaction_id = 1
    
    # Transactions matched (1:1 avec factures)
    for _, row in invoice_splits['matched'].iterrows():
        transactions.append({
            'TRANSACTION_ID': transaction_id,
            'AMOUNT': row['AMOUNT_TO_PAY'],
            'DATE': row['PAYMENT_DATE'],
            'LABEL': f"VIR {row['INVOICE_NUMBER']}",
            'REFERENCE': row['INVOICE_NUMBER'],
            'TYPE': 'MATCHED',
            'INVOICE_ID': row.name + 1  # +1 car l'ID commence à 1
        })
        transaction_id += 1
    
    # Transactions partial (paiements partiels)
    for _, row in invoice_splits['partial'].iterrows():
        partial_payments = random.randint(2, 4)
        remaining = row['AMOUNT_TO_PAY']
        
        for i in range(partial_payments):
            amount = round(remaining / (partial_payments - i), 2) if i != partial_payments - 1 else remaining
            remaining -= amount
            
            transactions.append({
                'TRANSACTION_ID': transaction_id,
                'AMOUNT': amount,
                'DATE': row['PAYMENT_DATE'] + timedelta(days=random.randint(0, 30)),
                'LABEL': f"VIR PARTIEL {row['INVOICE_NUMBER']}",
                'REFERENCE': f"{row['INVOICE_NUMBER']}-{i+1}",
                'TYPE': 'PARTIAL',
                'INVOICE_ID': row.name + 1
            })
            transaction_id += 1
    
    # Transactions grouped (regroupements)
    grouped_invoices = invoice_splits['grouped']
    chunks = [grouped_invoices[i:i+3] for i in range(0, len(grouped_invoices), 3)]
    
    for chunk in chunks:
        total = chunk['AMOUNT_TO_PAY'].sum()
        refs = ",".join(chunk['INVOICE_NUMBER'])
        
        transactions.append({
            'TRANSACTION_ID': transaction_id,
            'AMOUNT': total,
            'DATE': chunk.iloc[0]['PAYMENT_DATE'] + timedelta(days=random.randint(0, 5)),
            'LABEL': f"VIR MULTI {len(chunk)} FAC",
            'REFERENCE': refs,
            'TYPE': 'GROUPED',
            'INVOICE_ID': ",".join([str(x + 1) for x in chunk.index])  # IDs séparés par des virgules
        })
        transaction_id += 1
    
    # Transactions unmatched (sans référence claire)
    for _, row in invoice_splits['unmatched'].iterrows():
        transactions.append({
            'TRANSACTION_ID': transaction_id,
            'AMOUNT': row['AMOUNT_TO_PAY'],
            'DATE': row['PAYMENT_DATE'],
            'LABEL': fake.bs().upper(),
            'REFERENCE': fake.bothify(text="????#####"),
            'TYPE': 'UNMATCHED',
            'INVOICE_ID': row.name + 1
        })
        transaction_id += 1
    
    return pd.DataFrame(transactions)

def save_datasets(invoice_splits, bank_transactions):
    # Sauvegarde des factures
    invoice_splits['matched'].to_csv('invoices_output/invoices_matched.csv', index=False)
    invoice_splits['partial'].to_csv('invoices_output/invoices_partial_payments.csv', index=False)
    invoice_splits['grouped'].to_csv('invoices_output/invoices_grouped_payments.csv', index=False)
    invoice_splits['unmatched'].to_csv('invoices_output/invoices_unmatched.csv', index=False)
    
    # Sauvegarde des transactions
    bank_transactions[bank_transactions['TYPE'] == 'MATCHED'].to_csv(
        'invoices_output/bank_transactions_matched.csv', index=False)
    bank_transactions[bank_transactions['TYPE'] == 'PARTIAL'].to_csv(
        'invoices_output/bank_transactions_partial_payments.csv', index=False)
    bank_transactions[bank_transactions['TYPE'] == 'GROUPED'].to_csv(
        'invoices_output/bank_transactions_grouped_payments.csv', index=False)
    bank_transactions[bank_transactions['TYPE'] == 'UNMATCHED'].to_csv(
        'invoices_output/bank_transactions_unmatched.csv', index=False)

def main():
    print("Génération des factures de base...")
    df_invoices = generate_all_invoices(NUM_INVOICES)
    
    print("Découpage des factures en catégories...")
    invoice_splits = split_invoices(df_invoices)
    
    print("Génération des transactions bancaires...")
    bank_transactions = generate_bank_transactions(invoice_splits)
    
    print("Sauvegarde des fichiers...")
    save_datasets(invoice_splits, bank_transactions)
    
    print(f"""Génération terminée. Fichiers créés dans invoices_output/ :
    - Factures :
      * invoices_matched.csv ({len(invoice_splits['matched'])})
      * invoices_partial_payments.csv ({len(invoice_splits['partial'])})
      * invoices_grouped_payments.csv ({len(invoice_splits['grouped'])})
      * invoices_unmatched.csv ({len(invoice_splits['unmatched'])})
    - Transactions :
      * bank_transactions_matched.csv ({len(bank_transactions[bank_transactions['TYPE'] == 'MATCHED'])})
      * bank_transactions_partial_payments.csv ({len(bank_transactions[bank_transactions['TYPE'] == 'PARTIAL'])})
      * bank_transactions_grouped_payments.csv ({len(bank_transactions[bank_transactions['TYPE'] == 'GROUPED'])})
      * bank_transactions_unmatched.csv ({len(bank_transactions[bank_transactions['TYPE'] == 'UNMATCHED'])})
    """)

if __name__ == "__main__":
    main()