import os
import fitz  # PyMuPDF

output_dir = r"c:\Users\admin\Downloads\Research Assistant test\Research_Assistant\sample_papers"
os.makedirs(output_dir, exist_ok=True)

papers = [
    {
        "filename": "Attention_Is_All_You_Need_Transformer_Architecture.pdf",
        "title": "Attention Is All You Need: Scalable Sequence Transduction via Self-Attention",
        "authors": "Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit",
        "venue": "Advances in Neural Information Processing Systems (NeurIPS 2017)",
        "content": [
            ("ABSTRACT", "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder. The best performing models also connect the encoder and decoder through an attention mechanism. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely. Experiments on two machine translation tasks show these models to be superior in quality while being more parallelizable and requiring significantly less time to train."),
            ("1. INTRODUCTION", "Recurrent neural models, particularly long short-term memory (LSTM) and gated recurrent (GRU) neural networks, have been firmly established as state of the art approaches in sequence modeling and transduction problems such as language modeling and machine translation. Subsequent work has continued to push the boundaries of recurrent language models and encoder-decoder architectures. However, sequential computation remains a fundamental bottleneck in training efficiency."),
            ("2. MODEL ARCHITECTURE", "The Transformer follows this overall architecture using stacked self-attention and point-wise, fully connected layers for both the encoder and decoder. The encoder is composed of a stack of N = 6 identical layers. Each layer has two sub-layers. The first is a multi-head self-attention mechanism, and the second is a simple, position-wise fully connected feed-forward network. Multi-Head Attention allows the model to jointly attend to information from different representation subspaces at different positions."),
            ("3. EXPERIMENTS & RESULTS", "On the WMT 2014 English-to-German translation task, the big transformer model achieves a state-of-the-art BLEU score of 28.4, outperforming existing best models including ensembles by over 2.0 BLEU. On the WMT 2014 English-to-French translation task, our model establishes a new single-model state-of-the-art BLEU score of 41.8 after training for 3.5 days on eight GPUs."),
            ("4. RESEARCH GAPS & FUTURE WORK", "While the Transformer demonstrates superior training speed and translation performance, long-context attention scales quadratically with sequence length O(N^2). Future research must address linear self-attention approximations, memory-efficient attention kernels, and cross-modal adaptation for multimodal scientific inputs."),
            ("5. CONCLUSION", "In this work, we presented the Transformer, the first sequence transduction model based entirely on attention, replacing the recurrent layers most commonly used in encoder-decoder architectures with multi-headed self-attention.")
        ]
    },
    {
        "filename": "Quantum_Computing_Error_Correction_Surface_Codes.pdf",
        "title": "Fault-Tolerant Quantum Computing with Surface Code Error Mitigation",
        "authors": "Elena Rostova, Marcus Vance, David K. Chen",
        "venue": "Physical Review X - Quantum Information Systems (2024)",
        "content": [
            ("ABSTRACT", "Quantum error correction (QEC) is essential for realizing scalable fault-tolerant quantum computers. Surface codes represent the most promising paradigm due to their 2D nearest-neighbor connectivity requirements and high fault-tolerance thresholds (~1%). In this work, we demonstrate physical qubit layout strategies that suppress logical error rates below 10^-6 per cycle under realistic noise models."),
            ("1. INTRODUCTION", "Noisy Intermediate-Scale Quantum (NISQ) devices suffer from decoherence, gate infidelity, and crosstalk. To achieve practical quantum advantage in chemistry and cryptography, fault-tolerant operations backed by quantum error correction codes are strictly necessary."),
            ("2. SURFACE CODE ARCHITECTURE", "We deploy rotated surface codes where physical qubits are arranged in a 2D square lattice. Data qubits store logical information while measure qubits extract error syndromes through periodic X-type and Z-type stabilizer measurements."),
            ("3. EXPERIMENTAL PERFORMANCE", "Using real-time minimum-weight perfect matching (MWPM) decoders, we demonstrate syndrome decoding latency under 200 nanoseconds, maintaining high fault-tolerance operational fidelity across 127 transmon superconducting qubits."),
            ("4. RESEARCH GAPS & LIMITATIONS", "Physical qubit overhead remains significant, requiring thousands of physical qubits per logical qubit. High-temperature operation and optical interconnects remain major open challenges for multi-chip quantum scaling."),
            ("5. CONCLUSION", "Surface code error mitigation offers a realistic pathway toward sub-threshold logical qubit memory, establishing a blueprint for large-scale fault-tolerant quantum processors.")
        ]
    },
    {
        "filename": "CRISPR_Cas9_Gene_Editing_Therapy_Oncology.pdf",
        "title": "Precision CRISPR-Cas9 Gene Editing for Targeted Cancer Immunotherapy",
        "authors": "Sarah L. Jenkins, Hiroshi Tanaka, Maria E. Garcia",
        "venue": "Nature Biotechnology & Precision Oncology (2025)",
        "content": [
            ("ABSTRACT", "CRISPR-Cas9 technology has revolutionized genome editing by enabling precise modifications in target DNA sequences. This paper evaluates lipid nanoparticle (LNP) mediated delivery of Cas9 mRNA and sgRNA targeting immunosuppressive checkpoints in chimeric antigen receptor (CAR) T-cells for solid tumor oncology."),
            ("1. INTRODUCTION", "Adoptive cell therapy with CAR T-cells has shown remarkable efficacy in hematologic malignancies, but encounters microenvironmental barriers in solid tumors. Disruption of immune checkpoint genes such as PDCD1 (PD-1) via gene editing restores T-cell effector functions."),
            ("2. METHODOLOGY & DELIVERY", "We engineered electroporation-free LNP formulations encapsulating Cas9 ribonucleoprotein (RNP) complexes. In vitro knock-out efficiency exceeded 92% in primary human T-cells without compromising cell viability."),
            ("3. RESULTS & CLINICAL IMPLICATIONS", "In xenograft mouse models of glioblastoma, CRISPR-edited CAR T-cells demonstrated sustained tumor regression, enhanced cytokine production (IFN-gamma, IL-2), and prolonged persistence compared to unedited controls."),
            ("4. RESEARCH GAPS & ETHICAL CONSIDERATIONS", "Off-target cleavage risks and potential chromosomal translocations require high-throughput unbiased off-target profiling (e.g., GUIDE-seq). Long-term clinical safety monitoring remains essential."),
            ("5. CONCLUSION", "Targeted disruption of inhibitory pathways using LNP-delivered CRISPR-Cas9 enhances anti-tumor activity of CAR T-cells, paving the way for next-generation cell immunotherapies.")
        ]
    }
]

for p in papers:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842) # A4
    
    # Header & Title
    rect = fitz.Rect(50, 40, 545, 802)
    y = 50
    
    page.insert_text((50, y), p["title"], fontsize=14, fontname="helv", color=(0, 0.2, 0.6))
    y += 24
    page.insert_text((50, y), f"Authors: {p['authors']}", fontsize=10, fontname="helv", color=(0.3, 0.3, 0.3))
    y += 16
    page.insert_text((50, y), f"Venue: {p['venue']}", fontsize=9, fontname="helv", color=(0.5, 0.5, 0.5))
    y += 25
    
    # Draw line
    page.draw_line(fitz.Point(50, y), fitz.Point(545, y), color=(0.8, 0.8, 0.8), width=1)
    y += 20
    
    for section_title, section_text in p["content"]:
        page.insert_text((50, y), section_title, fontsize=11, fontname="helv", color=(0.1, 0.1, 0.1))
        y += 18
        
        # Simple text wrapping block
        textbox = fitz.Rect(50, y, 545, y + 120)
        rc = page.insert_textbox(textbox, section_text, fontsize=9, fontname="helv", align=0)
        y += 85
        
    filepath = os.path.join(output_dir, p["filename"])
    doc.save(filepath)
    doc.close()
    print(f"Generated paper: {filepath}")
