export default function dateToNumber(datetimestring) {
    // Converts an ISO datetime string to an int with format YYYYMMDD
    return parseFloat(datetimestring.split("T")[0].slice(2).split("-").join(""));
  }
