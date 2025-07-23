"""
Générateur de données de factures pour le dossier invoices_output

"""

import os
import pandas as pd
import numpy as np
from faker import Faker
from datetime import datetime, timedelta
import random
from typing import List, Dict, Tuple

# Initialisation de Faker
fake = Faker('fr_FR')
random.seed(42)
np.random.seed(42)
Faker.seed(42)

class InvoiceDataGenerator:
    """Générateur de données de factures pour le dossier invoices_output."""
    
    def __init__(self):
        self.invoices = []
        self.bank_transactions = []
        self.nb_invoices = 1000
        self.nb_bank_transactions = 1500
        
        # Statuts de facture
        self.statuses = ['paid', 'unpaid', 'partially_paid', 'overdue', 'cancelled']
        
        # Types de factures
        self.types = ['invoice', 'credit_note', 'proforma', 'recurring']
        
        # Catégories de produits/services
        self.categories = [
            'IT_Services', 'Consulting', 'Software', 'Hardware', 'Maintenance',
            'Training', 'Hosting', 'Support', 'Development', 'Design'
        ]
        
        # Méthodes de paiement
        self.payment_methods = [
            'bank_transfer', 'credit_card', 'paypal', 'check', 'direct_debit'
        ]
        
        # Devises
        self.currencies = ['EUR', 'USD', 'GBP', 'CHF']
        
        # Taux de TVA
        self.vat_rates = [0, 5.5, 10, 20]
    
    def generate_invoice_number(self, index: int) -> str:
        """Génère un numéro de facture séquentiel."""
        year = datetime.now().year
        return f"INV-{year}-{1000 + index:04d}"
    
    def generate_dates(self) -> Tuple[str, str, str]:
        """Génère les dates d'émission, d'échéance et de paiement."""
        issue_date = fake.date_between(start_date='-2y', end_date='today')
        due_date = issue_date + timedelta(days=random.randint(15, 60))
        
        # 80% de chance que la facture soit payée
        if random.random() < 0.8:
            payment_date = fake.date_between(
                start_date=issue_date, 
                end_date=min(due_date + timedelta(days=30), datetime.now().date())
            )
        else:
            payment_date = None
            
        return issue_date, due_date, payment_date
    
    def generate_invoice(self, index: int) -> Dict:
        """Génère une facture."""
        issue_date, due_date, payment_date = self.generate_dates()
        amount_ht = round(random.uniform(100, 10000), 2)
        vat_rate = random.choice(self.vat_rates)
        vat_amount = round(amount_ht * vat_rate / 100, 2)
        amount_ttc = round(amount_ht + vat_amount, 2)
        
        # Déterminer le statut
        if payment_date:
            if payment_date <= due_date:
                status = 'paid'
            else:
                status = 'paid_late'
        else:
            if datetime.now().date() > due_date:
                status = 'overdue'
            else:
                status = 'unpaid'
        
        return {
            'invoice_id': index + 1,
            'invoice_number': self.generate_invoice_number(index),
            'client_name': fake.company(),
            'client_id': random.randint(1, 500),
            'issue_date': issue_date,
            'due_date': due_date,
            'payment_date': payment_date,
            'amount_ht': amount_ht,
            'vat_rate': vat_rate,
            'vat_amount': vat_amount,
            'amount_ttc': amount_ttc,
            'currency': random.choice(self.currencies),
            'status': status,
            'type': random.choice(self.types),
            'category': random.choice(self.categories),
            'payment_method': random.choice(self.payment_methods) if payment_date else None,
            'notes': fake.sentence() if random.random() > 0.7 else None,
            'created_at': fake.date_time_between(start_date='-2y', end_date='now'),
            'updated_at': fake.date_time_between(start_date='-1y', end_date='now')
        }
    
    def generate_bank_transaction(self, invoice: Dict) -> Dict:
        """Génère une transaction bancaire liée à une facture."""
        if not invoice['payment_date']:
            return None
            
        transaction_date = invoice['payment_date']
        
        # Générer un montant qui peut être partiel ou total
        if invoice['status'] == 'partially_paid':
            amount = round(invoice['amount_ttc'] * random.uniform(0.1, 0.9), 2)
        else:
            amount = invoice['amount_ttc']
        
        # Générer un libellé réaliste
        label_templates = [
            f"VIR {invoice['invoice_number']}",
            f"PAIEMENT FACTURE {invoice['invoice_number']}",
            f"REGLEMENT {invoice['invoice_number']}",
            f"FACTURE {invoice['invoice_number']}",
            f"VIREMENT {invoice['invoice_number']}",
            f"PRLV {invoice['client_name']}",
            f"CB {invoice['client_name']}"
        ]
        
        return {
            'transaction_id': len(self.bank_transactions) + 1,
            'invoice_id': invoice['invoice_id'],
            'invoice_number': invoice['invoice_number'],
            'transaction_date': transaction_date,
            'value_date': transaction_date,
            'amount': amount,
            'currency': invoice['currency'],
            'label': random.choice(label_templates),
            'reference': f"REF{random.randint(100000, 999999)}",
            'created_at': transaction_date
        }
    
    def generate_all_data(self):
        """Génère toutes les données de facturation."""
        print("Génération des factures...")
        self.invoices = [self.generate_invoice(i) for i in range(self.nb_invoices)]
        
        print("Génération des transactions bancaires...")
        self.bank_transactions = []
        for invoice in self.invoices:
            if invoice['payment_date']:
                # Générer entre 1 et 3 transactions par facture payée
                num_transactions = random.choices([1, 2, 3], weights=[0.8, 0.15, 0.05])[0]
                
                if num_transactions == 1:
                    # Une seule transaction pour le montant total
                    transaction = self.generate_bank_transaction(invoice)
                    if transaction:
                        self.bank_transactions.append(transaction)
                else:
                    # Plusieurs transactions pour simuler des paiements partiels
                    remaining_amount = invoice['amount_ttc']
                    for i in range(num_transactions):
                        if i == num_transactions - 1:
                            # Dernière transaction pour le solde restant
                            amount = remaining_amount
                        else:
                            # Montant partiel aléatoire
                            max_amount = remaining_amount - (num_transactions - i - 1) * 0.01
                            amount = round(random.uniform(0.01, max_amount), 2)
                        
                        # Créer une copie de la facture avec le montant partiel
                        partial_invoice = invoice.copy()
                        partial_invoice['amount_ttc'] = amount
                        partial_invoice['status'] = 'partially_paid' if i < num_transactions - 1 else 'paid'
                        
                        transaction = self.generate_bank_transaction(partial_invoice)
                        if transaction:
                            self.bank_transactions.append(transaction)
                        
                        remaining_amount -= amount
                        remaining_amount = round(remaining_amount, 2)
    
    def save_to_csv(self, output_dir: str = 'invoices_output'):
        """Sauvegarde les données dans des fichiers CSV."""
        print(f"\nSauvegarde des données dans le dossier '{output_dir}'...")
        
        # Créer le dossier de sortie s'il n'existe pas
        os.makedirs(output_dir, exist_ok=True)
        
        # Convertir les dates en chaînes pour l'export CSV
        def convert_dates(obj):
            if isinstance(obj, (datetime, datetime.date)):
                return obj.isoformat()
            return obj
        
        # Sauvegarder les factures
        invoices_df = pd.DataFrame(self.invoices)
        invoices_df.to_csv(f'{output_dir}/invoices_all.csv', index=False, date_format='%Y-%m-%d')
        print(f"  ✓ {len(self.invoices)} factures sauvegardées dans invoices_all.csv")
        
        # Sauvegarder les transactions bancaires
        if self.bank_transactions:
            transactions_df = pd.DataFrame(self.bank_transactions)
            transactions_df.to_csv(f'{output_dir}/bank_transactions_all.csv', index=False, date_format='%Y-%m-%d')
            print(f"  ✓ {len(self.bank_transactions)} transactions bancaires sauvegardées dans bank_transactions_all.csv")
            
            # Créer des fichiers séparés pour les transactions appariées et non appariées
            matched_transactions = [t for t in self.bank_transactions if 'invoice_id' in t and t['invoice_id'] is not None]
            unmatched_transactions = [t for t in self.bank_transactions if 'invoice_id' not in t or t['invoice_id'] is None]
            
            if matched_transactions:
                pd.DataFrame(matched_transactions).to_csv(
                    f'{output_dir}/bank_transactions_matched.csv', 
                    index=False, 
                    date_format='%Y-%m-%d'
                )
                print(f"  ✓ {len(matched_transactions)} transactions appariées sauvegardées dans bank_transactions_matched.csv")
            
            if unmatched_transactions:
                pd.DataFrame(unmatched_transactions).to_csv(
                    f'{output_dir}/bank_transactions_unmatched.csv', 
                    index=False, 
                    date_format='%Y-%m-%d'
                )
                print(f"  ✓ {len(unmatched_transactions)} transactions non appariées sauvegardées dans bank_transactions_unmatched.csv")
        
        # Créer des fichiers supplémentaires pour les factures par statut
        for status in self.statuses:
            status_invoices = [i for i in self.invoices if i['status'] == status]
            if status_invoices:
                pd.DataFrame(status_invoices).to_csv(
                    f'{output_dir}/invoices_{status}.csv', 
                    index=False, 
                    date_format='%Y-%m-%d'
                )
                print(f"  ✓ {len(status_invoices)} factures avec statut '{status}' sauvegardées dans invoices_{status}.csv")
        
        # Créer un fichier de synthèse
        self.generate_summary_report(output_dir)
    
    def generate_summary_report(self, output_dir: str):
        """Génère un rapport de synthèse des données générées."""
        report_path = os.path.join(output_dir, 'summary_report.txt')
        
        with open(report_path, 'w') as f:
            f.write("=== RAPPORT DE SYNTHÈSE DES DONNÉES DE FACTURATION ===\n\n")
            
            # Résumé des factures
            f.write("RÉSUMÉ DES FACTURES:\n")
            f.write(f"- Nombre total de factures: {len(self.invoices)}\n")
            
            # Répartition par statut
            status_counts = {}
            for invoice in self.invoices:
                status = invoice['status']
                status_counts[status] = status_counts.get(status, 0) + 1
            
            f.write("\nRépartition par statut:\n")
            for status, count in status_counts.items():
                f.write(f"  - {status}: {count} factures ({count/len(self.invoices)*100:.1f}%)\n")
            
            # Montants totaux
            total_ht = sum(i['amount_ht'] for i in self.invoices)
            total_ttc = sum(i['amount_ttc'] for i in self.invoices)
            total_tva = total_ttc - total_ht
            
            f.write(f"\nMontants totaux:\n")
            f.write(f"- Total HT: {total_ht:,.2f} €\n")
            f.write(f"- Total TVA: {total_tva:,.2f} €\n")
            f.write(f"- Total TTC: {total_ttc:,.2f} €\n")
            
            # Répartition par catégorie
            category_totals = {}
            for invoice in self.invoices:
                category = invoice['category']
                category_totals[category] = category_totals.get(category, 0) + invoice['amount_ttc']
            
            f.write("\nRépartition par catégorie (montant TTC):\n")
            for category, amount in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
                f.write(f"  - {category}: {amount:,.2f} € ({amount/total_ttc*100:.1f}%)\n")
            
            # Transactions bancaires
            if self.bank_transactions:
                f.write("\nRÉSUMÉ DES TRANSACTIONS BANCAIRES:\n")
                f.write(f"- Nombre total de transactions: {len(self.bank_transactions)}\n")
                
                total_transactions = sum(t['amount'] for t in self.bank_transactions)
                f.write(f"- Montant total des transactions: {total_transactions:,.2f} €\n")
                
                # Transactions appariées vs non appariées
                matched = [t for t in self.bank_transactions if 'invoice_id' in t and t['invoice_id'] is not None]
                unmatched = [t for t in self.bank_transactions if 'invoice_id' not in t or t['invoice_id'] is None]
                
                f.write(f"\nTransactions appariées: {len(matched)} ({len(matched)/len(self.bank_transactions)*100:.1f}%)\n")
                f.write(f"Transactions non appariées: {len(unmatched)} ({len(unmatched)/len(self.bank_transactions)*100:.1f}%)\n")
            
            # Date de génération
            f.write(f"\nGénéré le: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
        
        print(f"  ✓ Rapport de synthèse sauvegardé dans {report_path}")

if __name__ == "__main__":
    print("=== Générateur de données de facturation ===")
    print("Création du dossier 'invoices_output' avec des données de facturation...\n")
    
    # Créer une instance du générateur
    generator = InvoiceDataGenerator()
    
    # Générer les données
    generator.generate_all_data()
    
    # Sauvegarder les données dans des fichiers CSV
    generator.save_to_csv()
    
    print("\n=== Génération terminée avec succès ===")
    print("Les fichiers ont été enregistrés dans le dossier 'invoices_output'.")
