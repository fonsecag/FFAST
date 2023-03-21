config = {
    "modelColors": [
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#d62728",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
        "#bcbd22",
    ],
    "datasetColors": ["#FFFFFF", "#D0D0D0", "#909090", "#505050", "#101010",],
    "errorDistNKdePoints": 1000,
    "aggloNInitPoints": 10000,
    "clusterScheme": [
        {"type": "Agglo", "desc": "Coulomb", "nClusters": 10},
        {"type": "KMeans", "desc": "Energy", "nClusters": 4},
    ],
}
