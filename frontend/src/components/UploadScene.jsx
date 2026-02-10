import { Canvas, useFrame } from "@react-three/fiber";
import { useRef, useMemo } from "react";
import * as THREE from "three";

const WireframeBox = ({ progress = 0 }) => {
  const meshRef = useRef();
  const edgesRef = useRef();
  
  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.x += 0.003;
      meshRef.current.rotation.y += 0.005;
      
      // Scale based on progress
      const scale = 1 + (progress / 100) * 0.3;
      meshRef.current.scale.setScalar(scale);
    }
  });

  const geometry = useMemo(() => new THREE.BoxGeometry(2, 2, 2), []);
  const edges = useMemo(() => new THREE.EdgesGeometry(geometry), [geometry]);

  return (
    <group ref={meshRef}>
      <lineSegments ref={edgesRef}>
        <primitive object={edges} attach="geometry" />
        <lineBasicMaterial 
          attach="material" 
          color="#CCFF00" 
          transparent 
          opacity={0.8}
          linewidth={2}
        />
      </lineSegments>
      <mesh>
        <boxGeometry args={[2, 2, 2]} />
        <meshBasicMaterial color="#CCFF00" transparent opacity={0.05} />
      </mesh>
    </group>
  );
};

const FloatingParticles = ({ count = 50, progress = 0 }) => {
  const pointsRef = useRef();
  
  const particles = useMemo(() => {
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 10;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 10;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 10;
    }
    return positions;
  }, [count]);

  useFrame((state) => {
    if (pointsRef.current) {
      pointsRef.current.rotation.y += 0.001;
      pointsRef.current.rotation.x += 0.0005;
    }
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={count}
          array={particles}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial 
        color="#CCFF00" 
        size={0.05} 
        transparent 
        opacity={0.6 + (progress / 100) * 0.4}
        sizeAttenuation
      />
    </points>
  );
};

const UploadScene = ({ progress = 0 }) => {
  return (
    <div className="absolute inset-0 pointer-events-none" data-testid="upload-3d-scene">
      <Canvas
        camera={{ position: [0, 0, 6], fov: 50 }}
        style={{ background: "transparent" }}
      >
        <ambientLight intensity={0.5} />
        <WireframeBox progress={progress} />
        <FloatingParticles count={100} progress={progress} />
      </Canvas>
    </div>
  );
};

export default UploadScene;
