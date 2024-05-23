export var dataSources = {
    ARPS: {
        validBands: ["dataMask"],
        validate: function (sample) {
            return sample.dataMask;
        },
        inputs: {
            NDVI: {
                bands: ["SR3", "SR4"],
                calculate: function (sample) {
                    return (sample.SR4 - sample.SR3) / (sample.SR4 + sample.SR3);
                }
            }
        }
    },
    S2L2A: {
        validBands: ["dataMask", "SCL"],
        validate: function (sample) {
            // Define codes as invalid:
            const invalid = [
                0, // NO_DATA
                1, // SATURATED_DEFECTIVE
                3, // CLOUD_SHADOW
                7, // CLOUD_LOW_PROBA
                8, // CLOUD_MEDIUM_PROBA
                9, // CLOUD_HIGH_PROBA
                10 // THIN_CIRRUS
            ]
            return !invalid.includes(sample.SCL) && sample.dataMask
        },
        inputs: {
            NDVI: {
                bands: ["B04", "B08"],
                calculate: function (sample) {
                    return (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
                }
            }
        }
    }
}
