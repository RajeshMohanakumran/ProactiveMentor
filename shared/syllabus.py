"""RAG retriever — CBME syllabus. Works out of the box, no PDF needed."""

CBME = {
    "Anatomy": [
        "Upper limb — brachial plexus, axilla, shoulder, elbow joints",
        "Lower limb — femoral triangle, sciatic nerve, knee, hip joints",
        "Thorax — heart chambers, coronary arteries, lungs, mediastinum",
        "Abdomen — peritoneum, liver, portal circulation, kidneys, suprarenal",
        "Head & neck — cranial nerves, thyroid, parathyroid, eye, ear, larynx",
        "Neuroanatomy — cerebral cortex, basal ganglia, cerebellum, tracts, meninges",
        "Embryology — cardiovascular, gut, limb, CNS, face development",
        "Histology — epithelium, connective tissue, muscle, nerve tissues",
    ],
    "Physiology": [
        "Blood — RBC, WBC, platelets, haemostasis, coagulation, blood groups",
        "Cardiovascular — cardiac cycle, output, ECG, blood pressure regulation",
        "Respiratory — mechanics, volumes, gas exchange, transport, hypoxia",
        "Renal — GFR, tubular reabsorption, acid-base balance, osmoregulation",
        "Endocrine — pituitary, thyroid, adrenal, pancreas, calcium regulation",
        "Nervous system — neuromuscular junction, synaptic transmission, reflexes",
        "GI — motility, secretion, digestion, absorption, liver physiology",
        "Reproductive — menstrual cycle, pregnancy, lactation physiology",
    ],
    "Biochemistry": [
        "Carbohydrate metabolism — glycolysis, TCA cycle, gluconeogenesis, glycogen",
        "Lipid metabolism — beta-oxidation, ketogenesis, lipoproteins, cholesterol",
        "Protein & amino acid metabolism — urea cycle, transamination, inborn errors",
        "Enzymes — kinetics, inhibition, isoenzymes, clinical enzymology",
        "Vitamins — fat soluble (ADEK), water soluble (B complex, C), deficiencies",
        "Molecular biology — DNA replication, transcription, translation, mutations",
        "Clinical biochemistry — LFT, KFT, lipid profile, blood glucose interpretation",
        "Minerals & nutrition — iron metabolism, BMR, nutritional requirements",
    ],
    "Pathology": [
        "Cell injury — reversible, irreversible, necrosis types, apoptosis",
        "Inflammation — acute, chronic, granulomatous, wound healing",
        "Haematology — anaemias classification, leukaemias, lymphomas, bleeding disorders",
        "Cardiovascular — atherosclerosis, MI pathology, hypertensive changes, cardiomyopathy",
        "Respiratory — pneumonia, tuberculosis, COPD, lung carcinoma",
        "GI pathology — peptic ulcer, IBD, hepatitis, cirrhosis, GI tumours",
        "Renal pathology — glomerulonephritis, nephrotic syndrome, renal tumours",
        "Neoplasia — carcinogenesis, tumour grading, staging, tumour markers",
    ],
    "Pharmacology": [
        "General pharmacology — pharmacokinetics (ADME), pharmacodynamics, drug interactions",
        "ANS pharmacology — adrenergic, cholinergic, blockers, clinical uses",
        "CVS drugs — antihypertensives, antiarrhythmics, antianginals, heart failure drugs",
        "Antimicrobials — beta-lactams, aminoglycosides, fluoroquinolones, antifungals",
        "CNS pharmacology — antiepileptics, antidepressants, antipsychotics, opioids",
        "NSAIDs & analgesics — mechanism, COX inhibition, clinical uses, adverse effects",
        "Endocrine pharmacology — insulin types, oral hypoglycaemics, thyroid drugs, steroids",
        "Chemotherapy — anticancer mechanisms, resistance, targeted therapy",
    ],
    "Microbiology": [
        "Gram-positive cocci — Staphylococcus, Streptococcus, virulence, infections",
        "Gram-negative organisms — E.coli, Klebsiella, Pseudomonas, Salmonella, Shigella",
        "Mycobacterium — tuberculosis, leprosy, culture methods, drug resistance",
        "Virology — Hepatitis A/B/C/D/E, HIV, Herpes viruses, Influenza, dengue",
        "Mycology — Candida, Aspergillus, Cryptococcus, dermatophytes",
        "Parasitology — Plasmodium life cycle, Entamoeba, Giardia, Toxoplasma, helminths",
        "Immunology — innate immunity, adaptive, hypersensitivity I–IV, autoimmunity",
        "Sterilisation, disinfection, hospital-acquired infections, antibiotic resistance",
    ],
    "Medicine": [
        "Cardiology — IHD, CCF, valvular diseases, pericarditis, infective endocarditis",
        "Respiratory — COPD, asthma, pneumonia, pleural effusion, ILD, sarcoidosis",
        "Gastroenterology — hepatitis, cirrhosis, portal hypertension, IBD, GI bleeding",
        "Endocrinology — diabetes mellitus, thyroid disorders, Cushing's, Addison's",
        "Nephrology — AKI, CKD, glomerulonephritis, nephrotic syndrome, UTI",
        "Neurology — stroke, epilepsy, Parkinson's, meningitis, Guillain-Barré",
        "Haematology — anaemia types, ITP, DIC, haemophilia, blood transfusion",
        "Rheumatology & connective tissue — RA, SLE, gout, osteoarthritis, vasculitis",
    ],
    "Surgery": [
        "Surgical anatomy — hernias (inguinal, femoral, umbilical), thyroid, breast",
        "Trauma — ATLS principles, fractures, wound management, burns",
        "GI surgery — appendicitis, intestinal obstruction, peritonitis, colorectal carcinoma",
        "Hepatobiliary — gallstones, jaundice types, acute pancreatitis, liver abscess",
        "Urology — renal calculi, BPH, carcinoma prostate, bladder tumours, hydronephrosis",
        "Vascular surgery — DVT, varicose veins, peripheral arterial disease, aneurysms",
        "Oncological surgery — staging, principles, specific cancers (thyroid, breast, stomach)",
        "Paediatric surgery — intussusception, Hirschsprung's, pyloric stenosis, congenital anomalies",
    ],
    "Obstetrics & Gynaecology": [
        "Antenatal care — ANC schedule, high-risk pregnancy, screening tests",
        "Normal labour — stages, mechanism, management, partograph",
        "Obstetric emergencies — PPH, eclampsia, shoulder dystocia, cord prolapse",
        "Antepartum complications — APH, placenta praevia, abruptio placentae, PIH",
        "Gynaecology — PCOS, uterine fibroids, endometriosis, PID",
        "Reproductive health — contraception methods, MTP act, infertility workup",
        "Gynaecological oncology — carcinoma cervix (HPV, staging), ovary, endometrium",
        "Neonatal care — APGAR scoring, birth asphyxia, neonatal jaundice, resuscitation",
    ],
    "Paediatrics": [
        "Growth & development — physical milestones, developmental milestones, assessment",
        "Neonatology — prematurity, respiratory distress, neonatal sepsis, jaundice",
        "Nutrition — protein-energy malnutrition, PEM grades, vitamin deficiency diseases",
        "Paediatric infections — measles, typhoid, meningitis, dengue in children",
        "Respiratory — pneumonia in children, asthma, bronchiolitis, croup",
        "Haematology — sickle cell disease, thalassaemia, ITP, haemophilia in children",
        "Immunisation — national immunisation schedule, cold chain, vaccine-preventable diseases",
        "Genetic disorders — Down syndrome, Turner's, Klinefelter's, inborn errors",
    ],
    "Community Medicine": [
        "Epidemiology — study designs, measures of frequency, disease causation, bias",
        "Biostatistics — mean, SD, normal distribution, hypothesis testing, p-value",
        "Communicable disease control — TB, malaria, HIV, vector-borne diseases",
        "Non-communicable diseases — DM, hypertension, cancer, cardiovascular prevention",
        "Nutrition programmes — ICDS, mid-day meal, POSHAN Abhiyan, deficiency disorders",
        "Environmental health — water quality, sanitation, air pollution, occupational health",
        "National health programmes — NHM, RNTCP, NVBDCP, RCH, NPCDCS",
        "Health system — PHC, CHC, district hospital, ASHA, health indicators",
    ],
}

ALL_SUBJECTS = list(CBME.keys()) + [
    "Ophthalmology", "ENT", "Psychiatry", "Dermatology", "Orthopaedics", "Radiology"
]


def get_syllabus_context(subjects: list) -> str:
    lines = []
    for s in subjects:
        matched = None
        for key in CBME:
            if key.lower() in s.lower() or s.lower() in key.lower():
                matched = key
                break
        if matched:
            lines.append(f"\n{matched}:")
            for t in CBME[matched]:
                lines.append(f"  - {t}")
        else:
            lines.append(f"\n{s}:\n  - Core {s} topics per CBME syllabus")
    return "\n".join(lines)
