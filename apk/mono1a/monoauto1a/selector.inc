    public static ExpoPair monoHudPair1A(CaptureController controller) {
        MonoExposurePlan1A p=controller.getMonoExposurePlan1A();
        return p==null?GenerateExpoPair(-1,controller):monoPair1A(p);
    }
    private static ExpoPair monoPair1A(MonoExposurePlan1A p) {
        ExpoPair pair=new ExpoPair(p.exposureNs,1,Long.MAX_VALUE,p.iso,1,Integer.MAX_VALUE,Integer.MAX_VALUE);
        pair.curlayer=ExpoPair.exposureLayer.Normal;pair.layerMpy=1;
        pair.isIsoLimited=(p.flags&1)!=0;pair.isShutterLimited=(p.flags&2)!=0;
        pair.isIsoManualOverLimit=(p.flags&4)!=0;pair.isShutterManualOverLimit=(p.flags&8)!=0;
        pair.isShutterTripodBypassed=(p.flags&16)!=0;
        return pair;
    }
    public static void setMonoPlannedExpo1A(CaptureRequest.Builder builder,int step,
            CaptureController controller,MonoExposurePlan1A plan) {
        if(plan==null) {setExpo(builder,step,controller);return;}
        ExpoPair pair=monoPair1A(plan);
        if(step==0) {fullpairs.clear();pairs.clear();}
        fullpairs.add(pair);if(pairs.size()<patternSize)pairs.add(pair);
        builder.set(CaptureRequest.CONTROL_AE_MODE,CaptureRequest.CONTROL_AE_MODE_OFF);
        builder.set(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION,0);
        builder.set(CaptureRequest.SENSOR_EXPOSURE_TIME,plan.exposureNs);
        builder.set(CaptureRequest.SENSOR_SENSITIVITY,plan.iso);
        builder.setTag(plan);
        lastSelectedExposure=plan.exposureNs;
    }
    private static final class MonoInput1A {
        final int iso,isoLow,isoHigh,analog;
        final long exposureNs,timeLow,timeHigh;
        final MonoExposurePlan1A.Controls controls;
        final double autoEv,dynamicFactor;
        MonoInput1A(int iso,long time,CameraCharacteristics chars,CaptureResult observation,
                MonoExposurePlan1A.Controls controls,double autoEv) {
            Range<Integer> sensitivity=chars.get(CameraCharacteristics.SENSOR_INFO_SENSITIVITY_RANGE);
            Range<Long> exposure=chars.get(CameraCharacteristics.SENSOR_INFO_EXPOSURE_TIME_RANGE);
            Integer a=chars.get(CameraCharacteristics.SENSOR_MAX_ANALOG_SENSITIVITY);
            if(sensitivity==null || exposure==null)throw new IllegalArgumentException("missing_physical_exposure_ranges");
            this.iso=iso;exposureNs=time;this.controls=controls;this.autoEv=autoEv;
            isoLow=sensitivity.getLower();isoHigh=sensitivity.getUpper();timeLow=exposure.getLower();timeHigh=exposure.getUpper();
            analog=a==null?isoHigh:a;
            if(isoLow<=0 || isoHigh<isoLow || timeLow<=0 || timeHigh<timeLow)throw new IllegalArgumentException("invalid_physical_exposure_ranges");
            dynamicFactor=getDynamicScalingFactor(controls.tripod,chars,observation);
        }
    }
    public static MonoExposurePlan1A planMonoExposure1A(CaptureController controller,CaptureResult transport,
            String cameraKey,long token,MonoExposurePlan1A.Controls controls) {
        if(transport==null)return null;
        Long ts=transport.get(CaptureResult.SENSOR_TIMESTAMP);
        com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A.PlanObservation1A entry=
                com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A.planObservation1A(cameraKey,ts==null?-1:ts);
        if(entry==null)return null;
        CaptureResult observation=entry.result;
        Integer iso=observation.get(CaptureResult.SENSOR_SENSITIVITY);
        Long exposure=observation.get(CaptureResult.SENSOR_EXPOSURE_TIME);
        Integer ae=observation.get(CaptureResult.CONTROL_AE_MODE);
        Integer aeComp=observation.get(CaptureResult.CONTROL_AE_EXPOSURE_COMPENSATION);
        if(iso==null || iso<=0 || exposure==null || exposure<=0 || ae==null || ae==0 || (aeComp!=null && aeComp!=0))return null;
        CameraCharacteristics chars=controller.monoCharacteristics1A();if(chars==null)return null;
        boolean eligible=MonoExposurePlan1A.assistEligible(controls);
        int rotation=PhotonCamera.getGravity()!=null?PhotonCamera.getGravity().getCameraRotation(controller.mSensorOrientation):controller.cameraRotation;
        M9BacklightDiagnostic.LiveFeedbackDecision feedback=M9M10rMfmTest1A.evaluateForMonoPlan1A(
                MonoExposurePlan1A.energy(iso,exposure)/1e9,rotation,eligible,
                eligible?"eligible_mono_shared_auto_plan":"mono_manual_ev_or_tripod_bypass");
        MonoInput1A input=new MonoInput1A(iso,exposure,chars,observation,controls,feedback.appliedEv);
        ExpoPair pair=generateMonoAware1A(-1,controller,input);
        // The manual values are physical sensor controls. Do not round through ISO-100 twice.
        if(controls.manualIso>0)pair.iso=Math.max(input.isoLow,Math.min(input.isoHigh,controls.manualIso));
        if(controls.manualExposureNs>0)pair.exposure=Math.max(input.timeLow,Math.min(input.timeHigh,controls.manualExposureNs));
        int flags=(pair.isIsoLimited?1:0)|(pair.isShutterLimited?2:0)|(pair.isIsoManualOverLimit?4:0)
                |(pair.isShutterManualOverLimit?8:0)|(pair.isShutterTripodBypassed?16:0);
        Long physicalTs=observation.get(CaptureResult.SENSOR_TIMESTAMP);
        Integer boost=observation.get(CaptureResult.CONTROL_POST_RAW_SENSITIVITY_BOOST);
        long now=android.os.SystemClock.elapsedRealtimeNanos();
        return new MonoExposurePlan1A(now,token,entry.receivedNs,physicalTs==null?-1:physicalTs,cameraKey,controls,
                iso,exposure,pair.iso,pair.exposure,boost==null||boost<=0?100:boost,feedback.appliedEv,feedback.reason,flags);
    }
