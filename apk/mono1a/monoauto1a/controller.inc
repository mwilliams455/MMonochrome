    // MONOAUTO1A_EXPOSUREPLAN: local camera/control lifetime, shared with the GL draw.
    private final MonoExposureStore1A monoExposureStore1A = new MonoExposureStore1A();
    public MonoExposureStore1A getMonoExposureStore1A() { return monoExposureStore1A; }
    public void invalidateMonoExposurePlan1A() { monoExposureStore1A.invalidate(); }
    public boolean useMonoExposurePlan1A() {
        return M9Config.usesM9Pipeline() && PhotonCamera.getSettings().selectedMode == CameraMode.PHOTO
                && !isDualSession && !mIsRecordingVideo && !mFlashed;
    }
    public String monoCameraKey1A() { return logicalID+"/"+physicalID; }
    public CameraCharacteristics monoCharacteristics1A() { return mCameraCharacteristicsMap.get(physicalID); }
    public MonoExposurePlan1A.Controls monoControls1A() {
        String metering=String.valueOf(System.identityHashCode(mCaptureSession));
        if(mPreviewRequestBuilder!=null) {
            metering+="|"+mPreviewRequestBuilder.get(CaptureRequest.SCALER_CROP_REGION);
            metering+="|"+java.util.Arrays.toString(mPreviewRequestBuilder.get(CaptureRequest.CONTROL_AE_REGIONS));
            if(Build.VERSION.SDK_INT>=30) metering+="|"+mPreviewRequestBuilder.get(CaptureRequest.CONTROL_ZOOM_RATIO);
        }
        return new MonoExposurePlan1A.Controls(PhotonCamera.getSettings().selectedMode.name(),
                paramController.getMonoUserEv1A(),(long)paramController.getCurrentExposureValue(),
                (int)paramController.getCurrentISOValue(),
                PhotonCamera.getGyro()!=null && PhotonCamera.getGyro().getTripod(),
                exposureBalanceMultiplier,exposureBalanceIsoLimit,exposureBalanceShutterLimit,oisMode,metering);
    }
    public MonoExposurePlan1A getMonoExposurePlan1A() {
        if(!useMonoExposurePlan1A()) return null;
        monoExposureStore1A.context(monoCameraKey1A(),monoControls1A());
        return monoExposureStore1A.latest(SystemClock.elapsedRealtimeNanos());
    }
    public MonoExposurePlan1A updateMonoExposurePlan1A(CaptureResult observation) {
        if(!useMonoExposurePlan1A()) {monoExposureStore1A.invalidate();return null;}
        MonoExposurePlan1A.Controls controls=monoControls1A();
        String camera=monoCameraKey1A();
        long token=monoExposureStore1A.context(camera,controls);
        MonoExposurePlan1A plan=IsoExpoSelector.planMonoExposure1A(this,observation,camera,token,controls);
        // Allocation can overlap a dial change/camera reopen: never publish across that boundary.
        monoExposureStore1A.context(monoCameraKey1A(),monoControls1A());
        return monoExposureStore1A.publish(plan,SystemClock.elapsedRealtimeNanos())?plan:null;
    }
    private MonoExposureStore1A.Selection selectMonoCapturePlan1A(long shutterNs) {
        if(!useMonoExposurePlan1A()) return null;
        monoExposureStore1A.context(monoCameraKey1A(),monoControls1A());
        MonoExposureStore1A.Selection selected=monoExposureStore1A.select(shutterNs);
        if(selected.plan!=null) return selected;
        // Correct current controls win over stale drawn controls. No hardware-AE exposure fallback.
        MonoExposurePlan1A fresh=updateMonoExposurePlan1A(mPreviewCaptureResult);
        return fresh==null?selected:new MonoExposureStore1A.Selection(fresh,
                "fresh_current_control_plan_not_yet_GL_drawn",-1,-1,MonoExposurePlan1A.boundedScale(fresh.previewScale()));
    }
