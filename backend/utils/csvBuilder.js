class CSVBuilder {
  /**
   * Convertit un tableau d'objets en CSV
   */
  static toCSV(data, headers = null) {
    if (!data || data.length === 0) {
      return '';
    }

    const keys = headers || Object.keys(data[0]);

    // Headers
    const csvHeaders = keys
      .map(key => this.escapeCSV(String(key)))
      .join(',');

    // Rows
    const csvRows = data
      .map(row =>
        keys
          .map(key => {
            const value = row[key];
            const strValue = value === null || value === undefined ? '' : String(value);
            return this.escapeCSV(strValue);
          })
          .join(',')
      )
      .join('\n');

    return `${csvHeaders}\n${csvRows}`;
  }

  /**
   * Échappe les valeurs CSV
   */
  static escapeCSV(value) {
    if (value === '' || value === null || value === undefined) {
      return '';
    }

    if (value.includes(',') || value.includes('"') || value.includes('\n')) {
      return `"${value.replace(/"/g, '""')}"`;
    }

    return value;
  }

  /**
   * Génère un filename avec timestamp
   */
  static generateFilename(tableName) {
    const timestamp = new Date().toISOString().split('T')[0];
    return `${tableName}_${timestamp}.csv`;
  }
}

module.exports = CSVBuilder;