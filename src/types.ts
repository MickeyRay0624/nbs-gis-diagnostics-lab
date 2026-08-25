export type Position = [number, number];

export type AoiGeometry =
  | { type: "Polygon"; coordinates: Position[][] }
  | { type: "MultiPolygon"; coordinates: Position[][][] };

export interface AoiProperties {
  shapeName: string;
  shapeID: string;
  shapeGroup: string;
  shapeType: string;
  boundaryYear: number;
  boundarySource: string;
  boundaryLicense: string;
  sourceURL: string;
}

export interface AoiFeature {
  type: "Feature";
  properties: AoiProperties;
  geometry: AoiGeometry;
}

export interface AoiFeatureCollection {
  type: "FeatureCollection";
  name: string;
  features: AoiFeature[];
}
