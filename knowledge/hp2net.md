## HP2NET: Empowering Efficient Phylogenetic Network Analysis through High-Performance Computing

Rafael Terra, Diego Carvalho, Denis Jacob Machado, Carla Osthoff, and Kary Oca˜na

Abstract—Advances in High-Performance Computing (HPC) have enabled increasingly complex genomic analyses, including those in phylogenomics. These analyses contribute to under- standing the evolution of viruses and pathogens, improving our knowledge of disease transmission, and supporting targeted public health strategies. However, due to the increasing number of tools and processing steps involved, executing these analyses manually, step by step, becomes error-prone and inefficient. To address this challenge, we present HP2NET, a robust framework for reproducible, efficient, and scalable phylogenetic network analysis. HP2NET integrates five workflows based on state-of- the-art tools such as PhyloNetworks and PhyloNet, allowing the analysis of multiple datasets and workflows in a single execution. The framework includes features such as task packaging and data reuse to improve performance and resource utilization in HPC environments. We perform a comprehensive performance evaluation of the software used within HP2NET, identifying bottlenecks and analyzing gains from parallel processing. Data reuse provided up to 15.35% time reduction, for a small dataset, in our experimental environment, while parallel execution of the five pipelines reduced total runtime by up to 90.96% compared to sequential runs. Finally, we validate HP2NET in a real-world case study by analyzing Dengue virus genomes, demonstrating its applicability value for large-scale phylogenetic analyses.

Index Terms—High-performance computing, parallel process- ing, scientific workflows, bioinformatics, phylogenetic analysis, Dengue virus

## I. INTRODUCTION

T HE landscape of genomics research drives significant advancements in high-throughput DNA sequencing, sup- ported by high-performance computing (HPC). This transfor- mation enhances our understanding of life sciences and means to fight diseases [1], [2]. For example, the National Institutes of Health (NIH) HPC system integrates robust data man- agement capabilities into its scientific applications, enabling researchers to process and analyze large-scale genomic data to extract relevant information. The NIH-Wide Strategic Plan for COVID-19 Research has significantly contributed to the global pandemic response [3]. Additionally, the role of viral genomics in fighting outbreaks of Zika virus (ZIKV) in Latin America,

Rafael Terra, Carla Osthoff, and Kary Oca˜na are with the National Laboratory of Scientific Computing, Rio de Janeiro, Brazil. (e-mail: rafaest@posgrad.lncc.br)

Diego Carvalho is with the Federal Center for Technological Education Celso Suckow da Fonseca, Rio de Janeiro, Brazil.

Denis Jacob Machado is with the University of North Carolina at Charlotte (UNC Charlotte), Department of Bioinformatics and Genomics (BiG) and the UNC Charlotte, Computational Intelligence Center to Predict Health and Environmental Risks (CIPHER) Research Center, Charlotte, NC, USA.

Yellow fever virus (YFV) in Angola and Brazil, West Nile virus (WNV) in the Americas, Chikungunya virus (CHIKV) in East Africa, and the ongoing Dengue virus (DENV) pandemic in the tropics and subtropics underscore the critical role of HPC to make sense of viral genomes [4].

HPC-accelerated phylogenetic methods provide critical in- sights into the evolution of viruses and pathogens, improving our understanding of disease spread and control and enhancing health outcomes through targeted public health strategies [5]. Building on these advancements, phylogenomics workflows [1], [2] can be integrated into scientific workflow management systems (SWfMSs) such as Pegasus [6] and NextFlow [7]. These systems, alongside language-parallel scripting libraries such as Swift [8] or Parsl [9], enhance workflow management, improving efficiency and scalability in phylogenomics, espe- cially in cloud environments and HPC clusters [10], [11].

Despite the growing capabilities of HPC and SWfMSs, the vast network space makes the reconstruction of phylogenetic networks challenging in phylogenetics and genome evolution. One approach is solving the minimum phylogenetic network problem, where phylogenetic trees are first inferred, and then the smallest network displaying all the trees is computed [12]. The most significant limitation of methods to infer introgres- sion and hybridization, including species network methods, is scalability. These methods have only been used with a handful of taxa and fewer than 200 loci [13]. Recent innovations incorporate reticulate evolutionary processes and reconstruct networks from ancestral profiles to improve phylogenetic network analyses [14], [15].

Effective modeling of scientific workflows, particularly in large-scale phylogenomics analyses, requires integrating several software programs, and dataflows and provenance management are particularly important. For example, [16] introduces a workflow for phylogenomics analysis, capable of constructing phylogenetic networks, but its scalability in HPC environments requires attention. Similarly, [17] utilizes rooted phylogenetic network algorithms to analyze coronavirus data and presents a pipeline model for hypothesis testing, yet scalability issues in HPC settings remain unexplored.

In this work, we present the HP2NET framework [18], [19], a comprehensive approach designed to streamline the construction of phylogenetic networks within HPC computing environments and, to the best of our knowledge, it is the only study focused on evaluating the execution of such software in an HPC environment. The main contributions of this work are as follows:


- Modeling of the HP2NET: the framework automates data manipulation across various stages of the phyloge- netic network construction, offering flexibility for deploy- ment on both local machines and computing clusters. This versatility enables users to construct multiple networks for one or more datasets within a single execution in- stance, maximizing resource utilization;

- Task packaging for pipeline execution: through a task packaging mechanism, HP2NET efficiently manages par- allelism, thereby reducing idle resources and runtime by prioritizing the execution of tasks with resolved depen- dencies;

- Development of a data reuse mechanism: HP2NET avoids the re-execution of identical tasks across different workflows, thereby enhancing efficiency;

- Exploratory analysis of performance and scalabil- ity: analyzing the framework’s performance to help re- searchers choose the most suitable approach for their needs.

- A case study based on Dengue virus genomic data: employed to demonstrate the practical utility and effec- tiveness of the HP2NET framework.

The manuscript is organized as follows. Section II intro- duces the background concepts relevant to the study. Section III describes the HP2NET framework and details the exper- imental setup. Section IV presents the results and analysis of the experiments, including the case study conducted using HP2NET. Finally, Section V summarizes the main findings and key insights derived from our research.

## II. BACKGROUND

## A. Phylogenetic Trees

The evolutionary relationship among a set of individuals can be represented through a structure called a phylogenetic tree, which consists of edges, internal nodes, leaves, and, in some cases, a root. The leaves represent the individuals being studied, such as genes, species, populations, or even DNA fragments. The internal nodes correspond to hypothetical ancestors, while the edges depict the evolutionary connections between individuals. The root, when present, represents the assumed common ancestor of all individuals in the tree [20].

There are many heuristics and approaches for constructing phylogenetic trees, as well as numerous software tools that implement these methods. However, for this work, we will focus on RAxML version 8.2.12 [21], IQ-TREE version 2.2 [22], MrBayes version 3.2.7a [23], ASTRAL version 3 [24], and Quartet MaxCut version 2.10 [25], which are integrated with the HP2NET framework.

RAxML and IQ-TREE both employ maximum likelihood (ML) for constructing phylogenetic trees, generating bootstrap replicates, and implementing evolutionary models. They effi- ciently handle large datasets through parallel and distributed computing on HPC clusters. RAxML operates in both se- quential and multi-threaded (pthreads) modes, while IQ-TREE optimizes CPU usage with the “-T AUTO” parameter. Both RAxML and IQ-TREE utilize branch swapping algorithms

to explore alternative tree topologies by iteratively swap- ping branches to potentially find better-scoring configurations. These tools also employ advanced scoring functions, such as likelihood functions in ML methods, to evaluate and optimize tree topologies. They start with heuristic initial trees and iteratively refine them to improve the overall likelihood score.

MrBayes is a software for constructing phylogenetic trees using Bayesian inference, offering support for complex datasets. It provides tools for summarizing analytical results, generating consensus trees, estimating model likelihoods, and calculating posterior probabilities [23]. In combination with MBSUM and BUCKy version 1.4.4 [26], MrBayes’ output can be summarized and used to construct quartet concordance factor tables, as demonstrated in the TICR pipeline [27].

Quartet MaxCut and ASTRAL serve related purposes, as they are both used to infer species trees. However, Quartet MaxCut uses a maximum-cut approach to infer these trees from quartets, while ASTRAL infers species trees by combin- ing gene trees.

## B. Phylogenetic Networks

Phylogenetic networks extend beyond traditional trees by representing complex scenarios like hybridization, horizontal gene transfer, and recombination, offering deeper insights into evolutionary dynamics within species or genes [28], [29]. In pathogenic organisms, these networks help unravel how genetic exchange shapes adaptation, virulence, and resistance, contributing to more effective strategies for disease surveil- lance, prevention, and treatment [17]. By capturing the com- plexity of genetic exchange, phylogenetic networks enhance our understanding of pathogen evolution.

Phylogenetic network software specializes in constructing, visualizing, and analyzing genetic data, with algorithms de- signed to handle reticulate events. This paper incorporates the Species Networks applying Quartets (SNaQ) algorithm [30] implemented in the PhyloNetworks package version 0.16.4 and PhyloNet version 3.8.4 [31], [32] into the architecture of HP2NET.

PhyloNet, implemented in Java, provides methods such as maximum parsimony, maximum likelihood, and maximum pseudo-likelihood for network construction based on rooted phylogenetic trees. It is used alongside the SNaQ algorithm, integrated into PhyloNetworks, which constructs phylogenetic networks from gene trees or quartet concordance factor tables, using a species tree as the initial topology. SNaQ, implemented in Julia, estimates networks using the maximum pseudo- likelihood approach and iteratively identifies the best network based on log-likelihood values. It also supports parallel exe- cution via Julia’s distributed module, allowing computations to be distributed across multiple processes [33].

## C. Parallel Workflows Using Parsl

The Parsl library enables the creation and management of parallel workflows, allowing task execution across diverse environments such as desktop computers, clusters, clouds, and supercomputers [9].


Parsl constructs a dynamic task dependency graph, or- chestrating the concurrent execution of tasks in the specified environment. By leveraging Python’s syntax, it enables parallel execution of both external programs and Python functions, using decorators like bash apps for external software and python apps for Python functions [9].

Parsl’s attributes include portability and modularization. Its programming logic and workflow execution configuration can be decoupled, supporting a myriad of architectures and config- urations (named executors and execution providers). Executors oversee controlled Python task execution, while execution providers facilitate script exchanges between resources. Parsl includes several executors, including the High Throughput Executor (HTEX). The HTEX, chosen in this work for its broad applicability, implements a pilot job model and is suitable for large-scale task execution [9].

## D. Dengue Viruses (DENV)

Dengue viruses (DENV) are the primary arboviral pathogens in tropical regions globally. DENV belongs to the Flavivirus genus within the Flaviviridae family. The DENV genome encodes three structural proteins (Capsid, Membrane, Envelope) and seven non-structural proteins (NS1, NS2A, NS2B, NS3, NS4A, NS4B, NS5). DENV consists of four dis- tinct serotypes (DENV-1 to DENV-4), each further subdivided into genotypes, associated with specific geographic regions and genetic variants [34].

## III. METHODS

## A. The HP2NET Framework

1) HP2NET Conceptual View: HP2NET is a high- performance computing framework designed for constructing phylogenetic trees and networks from gene sequence align- ments. The conceptual view is depicted in Fig. 1. Integrated with Parsl, HP2NET seamlessly combines well-established phylogenetic software, ensuring reproducibility, efficiency, and scalability across analyses. It supports infrastructure- independent deployment, enhancing versatility and accessibil- ity. For more details, The HP2NET framework is available on GitHub [35].

HP2NET offers an efficient, scalable, and flexible so- lution for phylogenetic network construction, achieved through five specialized workflows, referred to in this paper as RAXML-SNAQ, IQTREE-SNAQ, MRBAYES- SNAQ, RAXML-PHYLONET, and IQTREE-PHYLONET. Each workflow encompasses essential stages such as data preparation, phylogenetic tree inference, and network con- struction, all powered by high-performance computing and advanced workflow management systems.

## B. Parsl for Modeling HP2NET

HP2NET uses Parsl within the Python ecosystem to enhance task management and resource efficiency, similar to traditional Scientific Workflow Management Systems (SWfMS) [9]. This integration improves workflow flexibility and enables the incorporation of task packaging and data reuse mechanisms,

*Fig. 1. Conceptual view of HP2NET showing the five workflow configu- rations (RAXML-SNAQ, RAXML-PHYLONET, IQTREE-SNAQ, IQTREE- PHYLONET, MRBAYES-SNAQ). RAxML, IQ-TREE, and MrBayes run once per gene.*

*Fig. 2. Example of task packaging: the upper image represents the execution of two pipelines (colored green and blue, respectively) sequentially without task packaging. The lower image represents the same two pipelines; however, task packaging is applied.*

maximizing resource utilization and reducing computation time, as detailed below. Thanks to its modular design, the framework also supports easy integration of new workflows or adaptation of existing ones. Moreover, configuring different infrastructures is straightforward.

- 1) Task Packaging: Optimizes task execution when run- ning multiple workflows in parallel. The framework si- multaneously launches all workflows and executes tasks as long as their dependencies are resolved and sufficient resources are available. In other words, tasks are exe- cuted as soon as they are ready, without waiting for other tasks to complete. Fig. 2 provides a simplified example of how tasks are scheduled using task packaging.

- 2) Data Reuse: Although Parsl includes app caching, it only stores task results after execution, which can lead to race conditions, characterizing a problem in our scenario, as race conditions could affect file creation. To address this, we implemented a caching mechanism that stores a task’s future object instead of the result, preventing duplicate executions. As a result, the frame- work avoids redundant tasks by executing them only


*Fig. 3. Example of data reuse in a DAG: Concurrent execution of a dataset with 10 genes across multiple workflows in HP2NET framework.*

once when inputs are identical across workflows. For example, the Directed Acyclic Graph (DAG) in Fig. 3 shows the concurrent execution of HP2NET’s five workflows on a 10-gene dataset. Tasks like RAxML and IQ-TREE, common to multiple workflows, run once per gene, reducing redundancy and improving makespan.

The HP2NET framework optimizes phylogenetic network construction on HPC environments by processing multiple multisequence alignments, each representing a distinct gene, alongside a JSON metadata file containing essential infor- mation like outgroup taxa. HP2NET enables users to define workloads with multiple datasets and workflows, facilitat- ing parallel execution to maximize computational resources through data reuse and management. Ensuring reproducibility is critical in scientific experiments, and Parsl plays a pivotal role by logging and storing outputs from each app execution. This capability enables straightforward post mortem analysis, essential for validating and replicating experimental results.

The HP2NET framework, developed in Python v3.12.11 and powered by Parsl v1.3 for execution management, utilizes BioPython v1.75 [36] for biological data parsing and conver- sion. Additional functionalities are performed through scripts in other languages and specific dependencies. PhyloNetworks v0.14.3 operates with Julia v1.11.1, while ASTRAL v5.7.1 and PhyloNet v3.8.2 are executed using Java JDK v12. In our experiments, additional tasks are handled by IQ-TREE v2.2.0, RAxML v8.2.12, MrBayes v3.2.7a, Bucky v1.4.4, and Quartet Maxcut v2.10.

Installation of these tools on Linux-based systems is straightforward. Containerized versions of HP2NET are avail- able on Docker at https://hub.docker.com/repository/docker/ rafaelstjf/hp2net/general. Detailed installation instructions and troubleshooting guidance are provided on the framework’s GitHub repository.

## C. Experiments

In this section, we evaluate the performance and scala- bility of the HP2NET framework. HP2NET is designed to

handle gene sequence alignments efficiently, scaling naturally as the number of genes increases. The framework integrates sophisticated software that supports parallelism through multi- threading and offers flexible parameter combinations, optimiz- ing workflow efficiency.

1) Environment Setup: The experiments were conducted on the Santos Dumont (SDumont) supercomputer, using a computational node equipped with two Intel Xeon Cascade Lake Gold 6252 processors (24 physical cores per socket, totaling 48 cores with hyperthreading disabled), 384 GB of RAM, and running Red Hat Enterprise Linux 8.8 with Linux Kernel version 4.18. For more detailed specifications, please visit http://sdumont.lncc.br.

- 2) Computational Analyses of the HP2NET framework: We evaluated the performance and scalability of the HP2NET framework and identified bottlenecks within its software com- ponents using a benchmark dataset from the PhyloNetworks tutorial, available at https://github.com/crsl4/PhyloNetworks.jl/ wiki/Example-Data, comprising six taxa and 100 genes, each approximately 300 base pairs long. This dataset was selected because it clearly exposes the effects of task-level parallelism while keeping the total runtime short.

- 1) Performance of HP2NET and Software: To evaluate the framework’s behavior, the five workflows were ex- ecuted using a single Parsl worker, allowing only one task to run at a time. Software components that support multithreading (IQ-TREE, RAxML and SNaQ) were re- stricted to a single thread. After identifying bottlenecks, the multithreaded software components were analyzed individually by varying the number of threads from 1 to 24, the maximum per socket in the computational node.

- 2) Scalability of HP2NET and Workflows: Following the performance evaluation, we analyzed the scalability of HP2NET workflows by progressively increasing the number of workers from one to 48, within a single node, using the previously analyzed software configured with their optimal number of threads for the test scenario.

- 3) Biological Analysis with HP2NET: DENV Case Study: We used HP2NET to analyze DENV-1 genomes obtained from Brazil via a GenBank [37] search conducted on June 1st, 2023, using the keywords “(complete genome dengue virus type 1) AND brazil”. After excluding sequences lacking sampling date and location information, we identified 50 genomes of DENV-1 Genotype V, ranging from 10,179 base pairs (bp) to 10,917 bp. Filtering for human hosts, we selected 43 complete genomes for genotyping, phylogenetic tree construction, and network analysis. To ensure robust statistical support, our phylogenetic analysis included an outgroup dataset comprising West Nile Virus, Zika Virus, and DENV serotypes (specifically DENV-2 through DENV-4). Our network analysis focused on Zika Virus, emphasizing its relevance and divergence.

- 1) DENV-1 Genotyping Analysis: Using the Genome Detective software, which employs Blast and phyloge- netic methods, we identified the Dengue virus serotypes, genotypes, and major lineages in nucleotide sequences [38]. The genotyping analysis supported the classifica- tion of the genomes as DENV-1 Genotype V [38], [39].


- 2) DENV-1 Phylogenetic Analysis: We conducted a phy- logenetic analysis of complete genome sequences of DENV-1 using RAxML version 8.2.12 [21], with the GTR+G nucleotide substitution model. To assess tree topology robustness, we used the rapid bootstrapping al- gorithm with 1000 replicates and tree search commands (-f a) to explore tree space. Sequences were aligned using MAFFT [40] and manually curated with Aliview [41] to remove artifacts such as insertions, deletions, and gaps. Phylogenetic tree visualization utilized Phylo.io [42] and iTOL v6 [43].

## 3) DENV-1 Phylogenetic Networks:

We reduced the dataset of 43 DENV-1 genomes to 10 representative ones using the CD-HIT software [44] with a 0.99 similarity threshold to optimize computational resources in HP2NET. A Zika virus genome (accession number: MH882548) was used as an outgroup in the phylogenetic network construction process.

The genomes were annoted using the FLAVi (Fast Loci Annotation of Viruses) pipeline [45] for Flaviviruses. These annotated sequences were split by genes and were aligned using MAFFT version 7.453, with the default pa- rameters. The resulting alignments were converted into the NEXUS format, which are inputs in the HP2NET. The framework was executed using all the five work- flows, enabling the construction of phylogenetic net- works with Phylonet and SNaQ to detect reticulation

patterns in DENV-1.

## IV. RESULTS AND DISCUSSION

## A. Performance and Scalability of HP2NET

The runtime of each workflow executed with a single worker is shown in Fig. 4, with a breakdown of the time spent on different stages. Each stage consists of one or more executions of the same software using different (i.e., for a dataset with 100 genes, the time corresponds to running 100 independent executions of IQ-TREE). The figure highlights which stages, and consequently which software, have the greatest impact on overall execution time. The dominant stages include IQ-TREE, RAxML, SNaQ and MrBayes. From these software, RAxML, SNaQ, and IQ-TREE support internal parallelization, enabling more detailed performance analysis as the number of threads is varied, as further explored later in this section.

1) Performance oftheIQ-TREE Software: A comprehensive performance assessment was conducted by varying alignment lengths and the number of taxa, using IQ-TREE on three alignments: (I) 11 taxa with length 369 bp, (II) 6 taxa with 500 bp, and (III) 11 taxa with 2712 bp. The execution times for all datasets were similar to or even exceeded the sequential execution time as the number of threads increased. This phenomenon is likely due to the overhead generated by the software when parallelizing operations with short alignments. Therefore, for alignments of similar dimensions, utilizing more than one thread is unnecessary, as IQ-TREE efficiently handles the analysis sequentially and optimizes resource usage.

2) Performance ofthe RAxML Software: The three datasets previously used in IQ-TREE were also applied to RAxML.

*Fig. 4. Execution time for each workflow on a dataset of 100 genes and six taxa using one Parsl worker.*

While some datasets exhibited reduced execution times with multiple threads, the performance gain was minimal, and the additional overhead did not justify the use of parallelization. As a result, RAxML performed efficiently with the sequential version.

3) Performance of the SNaQ Software: Tests were con- ducted on two datasets to evaluate the parallel execution of the SNaQ algorithm: one with 11 taxa and 10 genes, and another with six taxa and 100 genes. Default settings were applied, including a maximum of three hybridizations and 10 runs. The results indicated that although parallelization showed some improvements, the number of threads used did not significantly affect the algorithm’s performance in this scenario.

4) Performance of the HP2NET Framework: Fig. 5 il- lustrates the average execution time for the five workflows executions and also when all of them are running concurrently in HP2NET, each repeated five times. The execution times for individual workflows exhibit similar patterns.

When running all five workflows concurrently, task pack- aging and reuse greatly improved performance, granting a 90.96% reduction in total execution time. decreasing from 62.67 to 5.67 minutes as the number of workers increased up to 48, for the tested dataset and for the used experi- mental environment.. This reduction was consistent across all workflows: IQTREE-SNAQ 47.86% (from 5.00 to 2.61 min- utes), RAxML-SNAQ 70.69% (from 11.66 to 3.42 minutes), IQTREE-PHYLONET 62.92% (from 3.90 to 1.45 minutes), RAxML-PHYLONET 76.73% (from 9.85 to 2.29 minutes), and MRBAYES-SNAQ 89.50% (from 43.61 to 4.58 minutes). The Friedman test [46] confirmed significant differences in execution times across workers for each workflow, with all p- values lower than 3.33×10−4, indicating that performance is strongly influenced by the number of workers.

The effect of data reuse can be better observed in Fig. 6 by comparing the two lines at one worker, representing sequential execution. While the theoretical execution time for the five workflows is 74.03 minutes, HP2NET completes the execution


Number of workers

*Fig. 5. Execution time per number of workers for the five HP2NET workflows on a dataset of 100 genes and six taxa. Curves: (1) IQTREE-SNAQ, (2) RAXML-SNAQ, (3) IQTREE-PHYLONET, (4) MRBAYES-SNAQ, (5) RAXML-PHYLONET. Red line: total HP2NET execution time.*

Number of workers

*Fig. 6. Execution time per number of workers for HP2NET on a dataset of 100 genes and six taxa. Red line: combined execution of all workflows using HP2NET; blue line: estimated sequential execution.*

in 62.67 minutes, achieving an approximate 15.35% reduction in execution time.

Fig. 7 shows the breakdown of execution stages when using 48 workers. Although the simultaneous execution of the five workflows is slower with one worker, the total time converges to that of the slowest workflow at 48 workers, with no significant difference between their execution times as indicated by a paired statistical test (p = 0.0625), highlighting the impact of task parallelism.

## B. Phylogeny and Network Analysis with HP2NET

1) DENV-1 Genotyping Analysis: Our analysis of 43 com- plete genomic sequences of DENV-1 strains from Brazil con- firms their classification as Genotype V, facilitating exploration of the reciprocal monophyly among DENV-1 genotypes. Five genotypes (I-V) of DENV-1 were previously identified using partial genomic sequences or the complete E gene [34].

Fig. 8 illustrates the phylogenetic tree with DENV-1 geno- types. The DENV-1 genomes from Brazil were identified as Genotype V (blue font/circles), revealing four main clades. Genome Detective reference sequence data are shown as follows: DENV-1 Genotype I (blue blocks/black font), DENV-

*Fig. 7. Execution time of the framework’s software when running each workflow using as input a dataset comprised of 100 genes and six taxa and 48 Parsl workers.*

1 Genotype II (red blocks/black font), DENV-1 Genotype III (yellow blocks/black font), DENV-1 Genotype IV (neon green blocks/black font), and DENV-1 Genotype V (turquoise block/black font).

2) DENV-1 Phylogenetic Analysis: The sequence align- ment, covering 11,208 bp and involving 43 taxa of DENV-1 Genotype V strains, alongside genomes of West Nile, Zika, and DENV serotypes (DENV-2 through DENV-4) as the out- group, was utilized for maximum likelihood (ML) tree search. The final ML optimization likelihood was -94858.748534. Our ML tree search yielded a topology similar to that of trees generated for genotyping analysis in Genome Detective using PAUP (Fig. 8).

In this tree, the DENV-1 Genotype V tree from Brazil exhibited four main clades, with sequences from different regions from Brazil. This finding corroborates a previously reported clade shift in the DENV-1 epidemic in Brazil [47]– [50].

3) DENV-1 Phylogenetic Networks: Fig. 9 displays the HP2NET networks when using all the workflows. These net- work topologies suggest the occurrence of hybridization events among taxa. The networks constructed using SNaQ, reticulate events involving DENV-1 ingroup taxa and the Zika outgroup were identified. Notably, sequences KP188543 and FJ850081 were implicated in reticulate events across all networks.

## V. CONCLUSION

In recent years, scientific workflows have become essen- tial tools in bioinformatics, enabling efficient orchestration of complex computational tasks within specialized High- Performance Computing (HPC) environments and Scientific Workflow Management Systems (SWfMS), enhancing re- source utilization, scalability, and accelerate discoveries in bioinformatics.

This work introduces HP2NET, a versatile framework de- signed for constructing phylogenetic networks. Leveraging


*Fig. 8. Phylogenetic Analysis of DENV-1 Genotype using Genome Detective.*

HPC capabilities, HP2NET enables parallel and distributed ex- ecution of diverse datasets and workflows. Its modular design allows for seamless addition of new components, enhancing flexibility and scalability for phylogenetic analyses.

In addition, this work conducts an initial study on Brazilian DENV-1 genomes, demonstrating genotyping and phyloge- netic analysis, including phylogenetic network construction using HP2NET.

In our computational experiments, the HP2NET framework demonstrated to be a robust tool for performing phylogenetic network construction using different methodologies. The si- multaneous execution of the five workflows using 48 workers, when compared to sequential execution, resulted in a reduction of up to 90.96% in total execution time, with execution times similar to the slowest execution of the isolated workflows. This reduction was a result of strategic design choices, such as data reuse, which showed a reduction of 15.35% in the execution time.

*Fig. 9. SNaQ and Phylonet networks for the dataset with 10 sequences of the DENV-1 virus genotype V. The color-coded lines (blue, red, and green) denote the same features within the networks.*

These results also highlight HP2NET’s potential for further scalability. In our experiments, its performance was con- strained by the phylogenetic network construction software, which represents the final stage of the execution and provides only a single task per workflow. The experiments were exe- cuted on a single node using 48 workers, the total number of physical cores available, given the scale of the study. Nevertheless, HP2NET supports multi-node execution, which becomes more effective for larger datasets with many genes and taxa. In such scenarios, both task-level parallelism and the internal parallelism of the supporting software can be more fully exploited, an aspect that will be explored in future work.

Genotyping analysis identified the genomes as genotype V, facilitating exploration of reciprocal monophyly among DENV-1 genotypes. Additionally, maximum likelihood phy- logenetic tree construction indicates a clade shift in Brazil’s DENV-1 epidemic, suggesting possible reticulate events. Sub- sequently, five phylogenetic networks were constructed, high- lighting reticulate events in the resultant networks.

In conclusion, the analysis of DENV-1 genomes reveals potential reticulate events, likely representing recombination or some form of horizontal gene transfer. However, further re- search is needed to confirm these findings and fully understand their implications.

## ACKNOWLEDGMENTS

HPC resources were generously provided by the National Laboratory of Scientific Computing (LNCC/Brazil) and the


Santos Dumont supercomputer. This research was funded by the National Council for Scientific and Technological Develop- ment (CNPq), specifically through the CNPq/MCTI/CT-Biotec project with Grant Number 440360/2022-6 and the University of North Carolina at Charlotte (UNC CHarlotte), Department of Bioinformatics and Genomics (BiG). Additionally, partial financial support was provided by the Coordination of Superior Level Staff Improvement (CAPES) Foundation, Brazil, under Finance Code 001.

## REFERENCES

- [1] D. de Oliveira and K. Oca˜na, “Parallel computing in genomic research: Advances and applications,” Advances and Applications in Bioinformat- ics and Chemistry, vol. 8, p. 23, Nov. 2015. doi: 10.2147/AABC.S64482

- [2] M. Djaffardjy, G. Marchment, C. Sebe, R. Blanchet, K. Belhajjame, A. Gaignard, F. Lemoine, and S. Cohen-Boulakia, “Developing and reusing bioinformatics data analysis pipelines using scientific workflow systems,” Computational and Structural Biotechnology Journal, vol. 21, pp. 2075–2085, 2023. doi: 10.1016/j.csbj.2023.03.003

- [3] J. Brase, N. Campbell, B. Helland, T. Hoang, M. Parashar, M. Rosen- field, J. Sexton, and J. Towns, “The COVID-19 high-performance computing consortium,” Computing in Science & Engineering, vol. 24, no. 1, pp. 78–85, 2022. doi: 10.1109/MCSE.2022.3145608

- [4] M. Girard, C. B. Nelson, V. Picot, and D. J. Gubler, “Arboviruses: A global public health threat,” Vaccine, vol. 38, no. 24, pp. 3989–3994, 2020. doi: 10.1016/j.vaccine.2020.04.011

- [5] J. Li, S. Wang, S. Rudinac, and A. Osseyran, “High-performance computing in healthcare: An automatic literature analysis perspective,” J. Big Data, vol. 11, no. 1, May 2024. doi: 10.1186/s40537-024-00929-2

- [6] E. Deelman, G. Singh, M.-H. Su, J. Blythe, Y. Gil, C. Kesselman, G. Mehta, K. Vahi, G. B. Berriman, J. Good et al., “Pegasus: A framework for mapping complex scientific workflows onto distributed systems,” Scientific Programming, vol. 13, no. 3, pp. 219–237, 2005. doi: 10.1155/2005/128026

- [7] P. Di Tommaso, M. Chatzou, E. W. Floden, P. P. Barja, E. Palumbo, and C. Notredame, “Nextflow enables reproducible computational work- flows,” Nature Biotechnology, vol. 35, no. 4, pp. 316–319, Apr. 2017. doi: 10.1038/nbt.3820

- [8] Y. Zhao, M. Hategan, B. Clifford, I. Foster, G. Von Laszewski, V. Nefe- dova, I. Raicu, T. Stef-Praun, and M. Wilde, “Swift: Fast, reliable, loosely coupled parallel computation,” in 2007 IEEE Congress on Ser- vices (Services 2007). IEEE, 2007. doi: 10.1109/SERVICES.2007.63 pp. 199–206.

- [9] Y. Babuji, A. Woodard, Z. Li, D. S. Katz, B. Clifford, R. Kumar, L. Lacinski, R. Chard, J. M. Wozniak, I. Foster et al., “Parsl: Per- vasive parallel programming in python,” in Proceedings of the 28th International Symposium on High-Performance Parallel and Distributed Computing, 2019. doi: 10.1145/3307681.3325400 pp. 25–36.

- [10] M. Mattoso, K. Oca˜na, F. Horta, J. Dias, E. Ogasawara, V. Silva, D. de Oliveira, F. Costa, and I. Ara´ujo, “User-steering of HPC work- flows: State-of-the-art and future directions,” in Proceedings of the 2nd ACM SIGMOD Workshop on Scalable Workflow Execution Engines and Technologies, ser. Sweet ’13. New York, New York and New York, NY, USA: Association for Computing Machinery, 2013. doi: 10.1145/2499896.2499900. ISBN 978-1-4503-2349-9

- [11] S. Cohen-Boulakia, K. Belhajjame, O. Collin, J. Chopard, C. Froide- vaux, A. Gaignard, K. Hinsen, P. Larmande, Y. L. Bras, F. Lemoine, F. Mareuil, H. M´enager, C. Pradal, and C. Blanchet, “Scientific work- flows for computational reproducibility in the life sciences: Status, challenges and opportunities,” Future Generation Computer Systems, vol. 75, pp. 284–298, 2017. doi: 10.1016/j.future.2017.01.012

- [12] L. Zhang, N. Abhari, C. Colijn, and Y. Wu, “A fast and scalable method for inferring phylogenetic networks from trees by aligning lineage taxon strings,” Genome Research, vol. 33, no. 7, pp. 1053–1060, Jul. 2023. doi: 10.1007/978-3-031-29119-7

- [13] R. A. L. Elworth, H. A. Ogilvie, J. Zhu, and L. Nakhleh, “Advances in computational methods for phylogenetic networks in the presence of hybridization,” in Bioinformatics and Phylogenetics: Seminal Contribu- tions of Bernard Moret, T. Warnow, Ed. Cham: Springer International Publishing, 2019, pp. 317–360, doi: 10.1007/978-3-030-10837-3 13.

- [14] A. Bai, P. L. Erd˝os, C. Semple, and M. Steel, “Defining phylogenetic networks using ancestral profiles,” Mathematical Biosciences, vol. 332, p. 108537, 2021. doi: 10.1016/j.mbs.2021.108537

- [15] C. Blair and C. An´e, “Phylogenetic trees and networks can serve as powerful and complementary approaches for analysis of genomic data,” Systematic Biology, vol. 69, no. 3, pp. 593–601, Sep. 2019. doi: 10.1093/sysbio/syz056

- [16] Y. Mao, S. Hou, J. Shi, and E. P. Economo, “TREEasy: An automated workflow to infer gene trees, species trees, and phylogenetic networks from multilocus data,” Molecular Ecology Resources, vol. 20, no. 3, pp. 832–840, May 2020. doi: 10.1111/1755-0998.13149

- [17] R. Wallin, L. van Iersel, S. Kelk, and L. Stougie, “Applicability of several rooted phylogenetic network algorithms for representing the evolutionary history of SARS-CoV-2,” BMC Ecol. Evol., vol. 21, no. 1, p. 220, Dec. 2021. doi: 10.1186/s12862-021-01946-y

- [18] R. Terra, M. Coelho, L. Cruz, M. Garcia-Zapata, L. Gadelha, C. Os- thoff, D. Carvalho, and K. Oca˜na, “Gerˆencia e An´alises de Work- flows aplicados a Redes Filogen´eticas de Genomas de Dengue no Brasil,” in Anais Do XV Brazilian E-Science Workshop (BRESCI 2021). Brasil: Sociedade Brasileira de Computac¸˜ao, Jul. 2021. doi: 10.5753/bresci.2021.15788 pp. 49–56.

- [19] R. Terra, K. Oca˜na, C. Osthoff, L. Cruz, P. Navaux, and D. Carvalho, “Framework para a Construc¸˜ao de Redes Filogen´eticas em Ambiente de Computac¸˜ao de Alto Desempenho,” in Anais Do XXIII Simp´osio Em Sistemas Computacionais de Alto Desempenho (SSCAD 2022). Brasil: Sociedade Brasileira de Computac¸˜ao, Oct. 2022. doi: 10.5753/ws- cad.2022.226366 pp. 73–84.

- [20] P. Lemey, M. Salemi, and A.-M. Vandamme, The Phylogenetic Handbook: A Practical Approach to Phylogenetic Analysis and Hypothesis Testing. 10.1017/CBO9780511819049. Cambridge University Press, 2009, doi:

- [21] A. Stamatakis, “RAxML version 8: A tool for phylogenetic analysis and post-analysis of large phylogenies,” Bioinformatics (Oxford, England), vol. 30, no. 9, pp. 1312–1313, May 2014. doi: 10.1093/bioinformatic- s/btu033

- [22] B. Q. Minh, H. A. Schmidt, O. Chernomor, D. Schrempf, M. D. Woodhams, A. Von Haeseler, and R. Lanfear, “IQ-TREE 2: New models and efficient methods for phylogenetic inference in the genomic era,” Molecular biology and evolution, vol. 37, no. 5, pp. 1530–1534, 2020. doi: 10.1093/molbev/msaa015

- [23] F. Ronquist, M. Teslenko, P. Van Der Mark, D. L. Ayres, A. Darling, S. H¨ohna, B. Larget, L. Liu, M. A. Suchard, and J. P. Huelsenbeck, “MrBayes 3.2: Efficient Bayesian phylogenetic inference and model choice across a large model space,” Systematic biology, vol. 61, no. 3, pp. 539–542, 2012. doi: 10.1093/sysbio/sys029

- [24] S. Mirarab, R. Reaz, M. S. Bayzid, T. Zimmermann, M. S. Swenson, and T. Warnow, “ASTRAL: Genome-scale coalescent-based species tree estimation,” Bioinformatics (Oxford, England), vol. 30, no. 17, pp. i541– i548, 2014. doi: 10.1093/bioinformatics/btu462

- [25] S. Snir and S. Rao, “Quartet MaxCut: A fast algorithm for amalgamating quartet trees,” Molecular phylogenetics and evolution, vol. 62, no. 1, pp. 1–8, 2012. doi: 10.1016/j.ympev.2011.06.021

- [26] B. R. Larget, S. K. Kotha, C. N. Dewey, and C. An´e, “BUCKy: Gene tree/species tree reconciliation with Bayesian concordance analysis,” Bioinformatics (Oxford, England), vol. 26, no. 22, pp. 2910–2911, Nov. 2010. doi: 10.1093/bioinformatics/btq539

- [27] N. W. Stenz, B. Larget, D. A. Baum, and C. An´e, “Exploring tree- like and non-tree-like patterns using genome sequences: An example using the inbreeding plant species Arabidopsis thaliana (L.) Heynh,” Systematic Biology, vol. 64, no. 5, pp. 809–823, 2015. doi: 10.1093/sys- bio/syv039

- [28] D. A. Morrison, “Networks in phylogenetic analysis: New tools for population biology,” International Journal for Parasitology, vol. 35, no. 5, pp. 567–582, 2005. doi: 10.1016/j.ijpara.2005.02.007

- [29] B. R. Holland, K. T. Huber, A. Dress, and V. Moulton, “Delta plots: A tool for analyzing phylogenetic distance data,” Molecular Biology and Evolution, vol. 30, no. 1, pp. 205–207, 2013. doi: 10.1093/oxfordjour- nals.molbev.a004030

- [30] C. Sol´ıs-Lemus and C. An´e, “Inferring Phylogenetic Networks with Maximum Pseudolikelihood under Incomplete Lineage Sorting,” PLOS Genetics, vol. 12, no. 3, p. e1005896, Mar. 2016. doi: 10.1371/jour- nal.pgen.1005896

- [31] Z. Cao, X. Liu, H. A. Ogilvie, Z. Yan, and L. Nakhleh, “Practical aspects of phylogenetic network analysis using PhyloNet,” bioRxiv : the preprint server for biology, 2019. doi: 10.1101/746362

- [32] D. Wen, Y. Yu, J. Zhu, and L. Nakhleh, “Inferring phylogenetic networks using PhyloNet,” Systematic biology, vol. 67, no. 4, pp. 735–740, 2018. doi: 10.1093/sysbio/syy015


- [33] C. Sol´ıs-Lemus, P. Bastide, and C. An´e, “PhyloNetworks: A package for phylogenetic networks,” Molecular biology and evolution, vol. 34, no. 12, pp. 3292–3298, 2017. doi: 10.1093/molbev/msx235

- [34] R. Chen and N. Vasilakis, “Dengue — Quo tu et quo vadis?” Viruses, vol. 3, no. 9, pp. 1562–1608, Sep. 2011. doi: 10.3390/v3091562

- [35] R. Terra, D. Carvalho, C. Osthoff, and K. Oca˜na, “Hp2net - high performance phylogenetic network,” Dec. 2025. [Online]. Available: https://doi.org/10.5281/zenodo.17791046

- [36] P. J. Cock, T. Antao, J. T. Chang, B. A. Chapman, C. J. Cox, A. Dalke, I. Friedberg, T. Hamelryck, F. Kauff, B. Wilczynski et al., “Biopython: Freely available Python tools for computational molecular biology and bioinformatics,” Bioinformatics (Oxford, England), vol. 25, no. 11, p. 1422, 2009. doi: 10.1093/bioinformatics/btp163

- [37] E. W. Sayers, J. Beck, E. E. Bolton, J. R. Brister, J. Chan, R. Connor, M. Feldgarden, A. M. Fine, K. Funk, J. Hoffman et al., “Database resources of the national center for biotechnology information in 2025,” Nucleic acids research, vol. 53, no. D1, pp. D20–D29, 2025. doi: 10.1093/nar/gkae979

- [38] M. Vilsker, Y. Moosa, S. Nooij, V. Fonseca, Y. Ghysens, K. Dumon, R. Pauwels, L. C. Alcantara, E. Vanden Eynden, A.-M. Vandamme, K. Deforche, and T. de Oliveira, “Genome Detective: An automated system for virus identification from high-throughput sequencing data,” Bioinformatics (Oxford, England), vol. 35, no. 5, pp. 871–873, Aug. 2018. doi: 10.1093/bioinformatics/bty695

J. Xavier, C. de Oliveira, T. Adelino, A. L. E. S. de Mello, T. Gr¨af, L. C. J. Alcantara, M. Giovanetti, and I. C. de Siqueira, “Phylogenetic reconstructions reveal the circulation of a novel Dengue virus-1V clade and the persistence of a Dengue virus-2 III genotype in northeast Brazil,” Viruses, vol. 15, no. 5, Apr. 2023. doi: 10.3390/v15051073

Carla Osthoff holds a degree in Electrical Engi- neering, as well as M.Sc. (1989) and Ph.D. (2000) degrees in Systems and Computer Engineering from the Federal University of Rio de Janeiro (UFRJ). Currently, she is a researcher and professor at the National Laboratory for Scientific Computing (LNCC), where she coordinates the National Center for High-Performance Processing and serves on the Santos Dumont Supercomputer Advisory Commit- tee. Her research interests include HPC, distributed systems, parallel processing, parallel I/O systems,

and scientific computing.

Diego Carvalho (M’98-SM’19) was born in Rio de Janeiro, Brazil in 1970. He received his B.S. de- gree in Production Engineering from UFRJ and the M.S. and Doctor’s degrees in Systems Engineering and Computer Science from PESC/COPPE. Since 2006, he has been a professor at the Department of Production Engineering of CEFET/RJ and his research interests include areas such as distributed systems, network engineering, parallel architectures, grid technologies, data mining and big data.

- [39] V. Fonseca, P. J. K. Libin, K. Theys, N. R. Faria, M. R. T. Nunes, M. I. Restovic, M. Freire, M. Giovanetti, L. Cuypers, A. Now´e, A. Abecasis, K. Deforche, G. A. Santiago, I. C. de Siqueira, E. J. San, K. C. B. Machado, V. Azevedo, A. M. B.-d. Filippis, R. V. da Cunha, O. G. Pybus, A.-M. Vandamme, L. C. J. Alcantara, and T. de Oliveira, “A computational method for the identification of Dengue, Zika and Chikun- gunya virus species and genotypes,” PLOS Neglected Tropical Diseases, vol. 13, no. 5, pp. 1–15, May 2019. doi: 10.1371/journal.pntd.0007231

- [40] K. Katoh and D. M. Standley, “MAFFT multiple sequence alignment software version 7: Improvements in performance and usability,” Molec- ular biology and evolution, vol. 30, no. 4, pp. 772–780, 2013. doi: 10.1093/molbev/mst010

- [41] A. Larsson, “AliView: A fast and lightweight alignment viewer and editor for large datasets,” Bioinformatics (Oxford, England), vol. 30, no. 22, pp. 3276–3278, Aug. 2014. doi: 10.1093/bioinformatics/btu531

- [42] O. Robinson, D. Dylus, and C. Dessimoz, “Phylo.Io : Interactive Viewing and Comparison of Large Phylogenetic Trees on the Web,” Molecular Biology and Evolution, vol. 33, no. 8, pp. 2163–2166, Aug. 2016. doi: 10.1093/molbev/msw080

- [43] I. Letunic and P. Bork, “Interactive Tree of Life (iTOL) v6: Recent updates to the phylogenetic tree display and annotation tool,” Nucleic Acids Research, vol. 52, no. W1, pp. W78–W82, Jul. 2024. doi: 10.1093/nar/gkae268

- [44] L. Fu, B. Niu, Z. Zhu, S. Wu, and W. Li, “CD-HIT: Accelerated for clustering the next-generation sequencing data,” Bioinformatics (Oxford, England), vol. 28, no. 23, pp. 3150–3152, Oct. 2012. doi: 10.1093/bioin- formatics/bts565

- [45] A. de Bernadi Schneider, D. Jacob Machado, S. Guirales, and D. A. Ja- nies, “FLAVi: An enhanced annotator for viral genomes of Flaviviridae,” Viruses, vol. 12, no. 8, p. 892, 2020. doi: 10.3390/v12080892

- [46] M. Friedman, “The use of ranks to avoid the assumption of nor- mality implicit in the analysis of variance,” Journal of the American Statistical Association, vol. 32, no. 200, pp. 675–701, 1937. doi: 10.1080/01621459.1937.10503522

- [47] A. Islam, F. Deeba, B. Tarai, E. Gupta, I. H. Naqvi, Mohd. Abdul- lah, R. Dohare, A. Ahmed, F. N. Almajhdi, T. Hussain, and e. al., “Global and local evolutionary dynamics of Dengue virus serotypes 1, 3, and 4,” Epidemiology and Infection, vol. 151, p. e127, 2023. doi: 10.1017/S0950268823000924

- [48] F. de Bruycker-Nogueira, T. M. A. Souza, T. Chouin-Carneiro, N. R. da Costa Faria, J. B. Santos, M. C. Torres, I. L. C. Ramalho, S. F. de Aguiar, R. M. R. Nogueira, A. M. B. de Filippis, and F. B. dos Santos, “DENV-1 Genotype V in Brazil: Spatiotemporal dispersion pattern reveals continuous co-circulation of distinct lineages until 2016,” Scientific Reports, vol. 8, 2018. doi: 10.1038/s41598-018-35622-x

Dr. Carvalho is a member of the Brazilian Asso-

ciation of Production Engineering, Brazilian Society for the Advancement of Science, and a senior member of IEEE.

Denis Jacob Machado Dr. Denis Jacob Machado was born in Brazil. He earned a B.S. in Biological Sciences from S˜ao Paulo State University (UNESP) in 2009, an M.Sc. in Zoology from the Univer- sity of S˜ao Paulo (USP) in 2012, and a Ph.D. in Bioinformatics from the University of S˜ao Paulo in 2018. He is an assistant professor at the Univer- sity of North Carolina at Charlotte, Department of Bioinformatics and Genomics, and an early member of the Computational Intelligence to Predict Health and Environmental Risks (CIPHER) research center.

He leads the Phyloinformatics Lab, focusing on pathogen evolution and biorepository data accessibility to support One Health initiatives.

Kary Oca˜na is a Senior Researcher at LNCC. She worked as a postdoctoral researcher at the Depart- ment of Computer Science, COPPE Institute, UFRJ, Brazil (2010-2015). Her postdoctoral fellowship was funded by FAPERJ (Postdoc Grade A) from 2013 to 2015. She received the Young Scientist of Our State award from FAPERJ (2017–2022).

She received her D.Sc. (2010) and M.Sc. (2006) in Cellular and Molecular Biology from FIOCRUZ (RJ-Brazil). Her research interests include bionfor- matics, scientific workflows, HPC, data analytics,

and machine learning.

Rafael Terra is a Ph.D. candidate in Computational Modeling at LNCC. Master’s degree in Computing Modeling from LNCC (2022), and B.Sc in Computer Science at Federal University of Juiz de Fora (2019). His interests cover scientific workflows, HPC, and bioinformatics.

- [49] G. d. O. Ribeiro, D. E. Gill, E. S. D. Ribeiro, F. J. C. Monteiro, V. S. Morais, R. Marcatti, M. O. d. S. Rego, E. L. L. Ara´ujo, S. S. Witkin, F. Villanova et al., “Adaptive evolution of new variants of dengue virus serotype 1 genotype V circulating in the brazilian amazon,” Viruses, vol. 13, no. 689, 2021. doi: 10.3390/v13040689

- [50] H. Fritsch, K. Moreno, I. A. B. Lima, C. S. Santos, B. G. G. Costa, B. L. de Almeida, R. A. Dos Santos, M. V. L. d. O. Francisco, M. P. S. Sampaio, M. M. de Lima, F. M. Pereira, V. Fonseca, S. Tosta,
