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
    for i in range(num_invoices):
        base_data = generate_invoice_base_data()
        status = random.choices(
            list(STATUS_DISTRIBUTION.keys()),
            weights=list(STATUS_DISTRIBUTION.values())
        )[0]
        
        payment_date = None
        if status == 'PAID':
            payment_date = base_data['EXPECTED_PAYMENT_DATE'] + timedelta(days=random.randint(-15, 15))
        
        invoice_data = {
            'INVOICE_ID': i + 1,  # ID explicite commençant à 1
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

def generate_bank_statements(invoice_splits):
    """Génère les relevés bancaires selon la structure BANK_STATEMENT"""
    statements = []
    statement_id = 1
    
    # Statements matched (1:1 avec factures)
    for _, row in invoice_splits['matched'].iterrows():
        statements.append({
            'STATEMENT_ID': statement_id,
            'STATEMENT_DATE': row['PAYMENT_DATE'],
            'OPERATION_LABEL': f"VIREMENT RECU",
            'ADDITIONAL_LABEL': f"REF: {row['INVOICE_NUMBER']} - {row['LABEL']}",
            'DEBIT': None,  # Pas de débit pour les encaissements
            'CREDIT': row['AMOUNT_TO_PAY'],
            'COMMENTS': f"Paiement facture {row['INVOICE_NUMBER']}",
            'RELATED_INVOICE_ID': row['INVOICE_ID'],
            'CREATED_AT': datetime.now(),
            'SOURCE_FILENAME': f"releve_{row['PAYMENT_DATE'].strftime('%Y%m')}.csv",
            'FILE_BLOB': None,  # Sera géré séparément si nécessaire
            'MIME_TYPE': 'text/csv',
            'RELATED_EXPENSE_ID': None,  # Pas de dépense pour les encaissements
            'VALUE_DATE': row['PAYMENT_DATE'],
            'MATCH_TYPE': 'MATCHED'
        })
        statement_id += 1
    
    # Statements partial (paiements partiels)
    for _, row in invoice_splits['partial'].iterrows():
        partial_payments = random.randint(2, 4)
        remaining = row['AMOUNT_TO_PAY']
        
        for i in range(partial_payments):
            amount = round(remaining / (partial_payments - i), 2) if i != partial_payments - 1 else remaining
            remaining -= amount
            payment_date = row['PAYMENT_DATE'] + timedelta(days=random.randint(0, 30))
            
            statements.append({
                'STATEMENT_ID': statement_id,
                'STATEMENT_DATE': payment_date,
                'OPERATION_LABEL': f"VIREMENT RECU",
                'ADDITIONAL_LABEL': f"PAIEMENT PARTIEL {i+1}/{partial_payments} - REF: {row['INVOICE_NUMBER']}",
                'DEBIT': None,
                'CREDIT': amount,
                'COMMENTS': f"Paiement partiel {i+1} facture {row['INVOICE_NUMBER']}",
                'RELATED_INVOICE_ID': row['INVOICE_ID'],
                'CREATED_AT': datetime.now(),
                'SOURCE_FILENAME': f"releve_{payment_date.strftime('%Y%m')}.csv",
                'FILE_BLOB': None,
                'MIME_TYPE': 'text/csv',
                'RELATED_EXPENSE_ID': None,
                'VALUE_DATE': payment_date,
                'MATCH_TYPE': 'PARTIAL'
            })
            statement_id += 1
    
    # Statements grouped (regroupements)
    grouped_invoices = invoice_splits['grouped']
    chunks = [grouped_invoices[i:i+3] for i in range(0, len(grouped_invoices), 3)]
    
    for chunk in chunks:
        total = chunk['AMOUNT_TO_PAY'].sum()
        refs = ", ".join(chunk['INVOICE_NUMBER'])
        invoice_ids = ",".join([str(x) for x in chunk['INVOICE_ID']])
        payment_date = chunk.iloc[0]['PAYMENT_DATE'] + timedelta(days=random.randint(0, 5))
        
        statements.append({
            'STATEMENT_ID': statement_id,
            'STATEMENT_DATE': payment_date,
            'OPERATION_LABEL': f"VIREMENT RECU",
            'ADDITIONAL_LABEL': f"PAIEMENT GROUPE {len(chunk)} FACTURES",
            'DEBIT': None,
            'CREDIT': total,
            'COMMENTS': f"Paiement groupé factures: {refs}",
            'RELATED_INVOICE_ID': chunk.iloc[0]['INVOICE_ID'],  # Première facture comme référence principale
            'CREATED_AT': datetime.now(),
            'SOURCE_FILENAME': f"releve_{payment_date.strftime('%Y%m')}.csv",
            'FILE_BLOB': None,
            'MIME_TYPE': 'text/csv',
            'RELATED_EXPENSE_ID': None,
            'VALUE_DATE': payment_date,
            'MATCH_TYPE': 'GROUPED',
            'GROUPED_INVOICE_IDS': invoice_ids  # Colonne supplémentaire pour tracer tous les IDs
        })
        statement_id += 1
    
    # Statements unmatched (sans référence claire)
    for _, row in invoice_splits['unmatched'].iterrows():
        statements.append({
            'STATEMENT_ID': statement_id,
            'STATEMENT_DATE': row['PAYMENT_DATE'],
            'OPERATION_LABEL': f"VIREMENT RECU",
            'ADDITIONAL_LABEL': fake.company().upper(),
            'DEBIT': None,
            'CREDIT': row['AMOUNT_TO_PAY'],
            'COMMENTS': f"Virement sans référence claire - {fake.bothify(text='????#####')}",
            'RELATED_INVOICE_ID': None,  # Pas de lien explicite
            'CREATED_AT': datetime.now(),
            'SOURCE_FILENAME': f"releve_{row['PAYMENT_DATE'].strftime('%Y%m')}.csv",
            'FILE_BLOB': None,
            'MIME_TYPE': 'text/csv',
            'RELATED_EXPENSE_ID': None,
            'VALUE_DATE': row['PAYMENT_DATE'],
            'MATCH_TYPE': 'UNMATCHED',
            'ACTUAL_INVOICE_ID': row['INVOICE_ID']  # Pour traçabilité dans le dataset
        })
        statement_id += 1
    
    # Ajout de quelques transactions de dépenses pour rendre plus réaliste
    for _ in range(200):  # 200 transactions de dépenses aléatoires
        expense_date = fake.date_between(start_date='-2y', end_date='today')
        statements.append({
            'STATEMENT_ID': statement_id,
            'STATEMENT_DATE': expense_date,
            'OPERATION_LABEL': random.choice(['PRELEVEMENT', 'VIREMENT EMIS', 'CHEQUE']),
            'ADDITIONAL_LABEL': random.choice([
                'ELECTRICITE', 'TELEPHONIE', 'FOURNITURES BUREAU', 
                'SALAIRES', 'CHARGES SOCIALES', 'LOYER'
            ]),
            'DEBIT': round(random.uniform(100, 5000), 2),
            'CREDIT': None,
            'COMMENTS': fake.sentence(nb_words=6),
            'RELATED_INVOICE_ID': None,
            'CREATED_AT': datetime.now(),
            'SOURCE_FILENAME': f"releve_{expense_date.strftime('%Y%m')}.csv",
            'FILE_BLOB': None,
            'MIME_TYPE': 'text/csv',
            'RELATED_EXPENSE_ID': random.randint(1, 50),  # ID de dépense fictif
            'VALUE_DATE': expense_date,
            'MATCH_TYPE': 'EXPENSE'
        })
        statement_id += 1
    
    return pd.DataFrame(statements)

def save_datasets(invoice_splits, bank_statements):
    # Sauvegarde des factures complètes
    all_invoices = pd.concat([
        invoice_splits['matched'],
        invoice_splits['partial'],
        invoice_splits['grouped'],
        invoice_splits['unmatched'],
        invoice_splits['non_paid']
    ], ignore_index=True)
    
    all_invoices.to_csv('invoices_output/all_invoices.csv', index=False)
    
    # Sauvegarde des factures par catégorie
    invoice_splits['matched'].to_csv('invoices_output/invoices_matched.csv', index=False)
    invoice_splits['partial'].to_csv('invoices_output/invoices_partial_payments.csv', index=False)
    invoice_splits['grouped'].to_csv('invoices_output/invoices_grouped_payments.csv', index=False)
    invoice_splits['unmatched'].to_csv('invoices_output/invoices_unmatched.csv', index=False)
    invoice_splits['non_paid'].to_csv('invoices_output/invoices_non_paid.csv', index=False)
    
    # Sauvegarde du relevé bancaire complet
    bank_statements.to_csv('invoices_output/bank_statements_all.csv', index=False)
    
    # Sauvegarde des relevés par type
    for match_type in bank_statements['MATCH_TYPE'].unique():
        subset = bank_statements[bank_statements['MATCH_TYPE'] == match_type]
        subset.to_csv(f'invoices_output/bank_statements_{match_type.lower()}.csv', index=False)

def main():
    print("Génération des factures de base...")
    df_invoices = generate_all_invoices(NUM_INVOICES)
    
    print("Découpage des factures en catégories...")
    invoice_splits = split_invoices(df_invoices)
    
    print("Génération des relevés bancaires...")
    bank_statements = generate_bank_statements(invoice_splits)
    
    print("Sauvegarde des fichiers...")
    save_datasets(invoice_splits, bank_statements)
    
    print(f"""Génération terminée. Fichiers créés dans invoices_output/ :
    
    FACTURES :
    - all_invoices.csv ({len(df_invoices)} factures au total)
    - invoices_matched.csv ({len(invoice_splits['matched'])})
    - invoices_partial_payments.csv ({len(invoice_splits['partial'])})
    - invoices_grouped_payments.csv ({len(invoice_splits['grouped'])})
    - invoices_unmatched.csv ({len(invoice_splits['unmatched'])})
    - invoices_non_paid.csv ({len(invoice_splits['non_paid'])})
    
    RELEVÉS BANCAIRES :
    - bank_statements_all.csv ({len(bank_statements)} lignes au total)
    - bank_statements_matched.csv ({len(bank_statements[bank_statements['MATCH_TYPE'] == 'MATCHED'])})
    - bank_statements_partial.csv ({len(bank_statements[bank_statements['MATCH_TYPE'] == 'PARTIAL'])})
    - bank_statements_grouped.csv ({len(bank_statements[bank_statements['MATCH_TYPE'] == 'GROUPED'])})
    - bank_statements_unmatched.csv ({len(bank_statements[bank_statements['MATCH_TYPE'] == 'UNMATCHED'])})
    - bank_statements_expense.csv ({len(bank_statements[bank_statements['MATCH_TYPE'] == 'EXPENSE'])})
    """)
    
    # Statistiques de validation
    print("\n=== STATISTIQUES DE VALIDATION ===")
    print(f"Total factures générées: {len(df_invoices)}")
    print(f"Factures payées: {len(invoice_splits['matched']) + len(invoice_splits['partial']) + len(invoice_splits['grouped']) + len(invoice_splits['unmatched'])}")
    print(f"Relevés avec RELATED_INVOICE_ID renseigné: {len(bank_statements[bank_statements['RELATED_INVOICE_ID'].notna()])}")
    print(f"Revenus totaux (CREDIT): {bank_statements['CREDIT'].sum():.2f} €")
    print(f"Dépenses totales (DEBIT): {bank_statements['DEBIT'].sum():.2f} €")

if __name__ == "__main__":
    main()