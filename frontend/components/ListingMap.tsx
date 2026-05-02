"use client";

import { GoogleMap, Marker, useJsApiLoader } from "@react-google-maps/api";

interface ListingMapProps {
  lat: number;
  lng: number;
  title: string;
}

const MAP_CONTAINER_STYLE = { width: "100%", height: "256px" };

export default function ListingMap({ lat, lng, title }: ListingMapProps) {
  const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY ?? "";

  const { isLoaded } = useJsApiLoader({
    googleMapsApiKey: apiKey,
  });

  if (!apiKey || !isLoaded) return null;

  const center = { lat, lng };

  return (
    <div className="rounded-xl overflow-hidden border border-stone-200">
      <GoogleMap
        mapContainerStyle={MAP_CONTAINER_STYLE}
        center={center}
        zoom={16}
        options={{
          disableDefaultUI: true,
          zoomControl: true,
          streetViewControl: false,
        }}
      >
        <Marker position={center} title={title} />
      </GoogleMap>
    </div>
  );
}
