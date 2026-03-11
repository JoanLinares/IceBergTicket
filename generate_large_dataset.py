import csv
import random
from faker import Faker

# Initialize Faker and random seed
fake = Faker()
Faker.seed(42)
random.seed(42)

# Define possible values for fields
queues = ['Technical Support', 'Customer Service', 'Billing', 'Sales', 'IT Support', 'Returns and Exchanges', 'General Inquiry']
priorities = ['low', 'medium', 'high']
types = ['Request', 'Incident']
languages = ['en', 'es', 'de', 'fr', 'pt']
tags = ['Bug', 'Feature', 'Crash', 'Security', 'Outage', 'Performance', 'Guidance', 'Documentation']

# File path for the dataset
output_file = 'ml/data/test_dataset_100k.csv'

# Generate dataset
with open(output_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    # Write header row
    writer.writerow(['subject', 'body', 'ticket_type', 'priority', 'language', 'queue', 'version', 'answer', 'tags'])
    
    # Write 100,000 rows of data
    for _ in range(100000):
        subject = fake.sentence()
        body = fake.paragraph(nb_sentences=5)
        ticket_type = random.choice(types)
        priority = random.choice(priorities)
        language = random.choice(languages)
        queue = random.choice(queues)
        version = round(random.uniform(1.0, 5.0), 1)
        answer = fake.paragraph(nb_sentences=3)
        tag_values = ', '.join(random.sample(tags, random.randint(0, len(tags))))
        
        row = [subject, body, ticket_type, priority, language, queue, version, answer, tag_values]
        writer.writerow(row)

print(f"Dataset with 100,000 rows created at {output_file}")